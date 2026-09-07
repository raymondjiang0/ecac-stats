"""Parser for InStat's SHOTS page (P6 for visitor, P14 for home).

Layout: per-player row with:
- jersey + name
- Goals (single int)
- Shots (total) / on-goal (with %)
- Shots blocking (single int — defensive blocks)
- 13 x/y% pairs for: PP, SH, positional attacks, counter attacks,
  slot, center, right flank, left flank, blue line right/center/left,
  slapshot, wrist shot

Column x-coordinate anchors (from fixture inspection):
  ~85.6   Goals
  ~114.0  Shots total/on-goal (x/y pair)
  ~166.9  Shots blocking (single int)
  ~196.7  Power play (x/y pair)
  ~246.7  Short-handed (x/y pair)
  ~275.0  In positional attacks (x/y pair)
  ~325.0  In counter-attacks (x/y pair)
  ~372.5  Slot (x/y pair)
  ~419.9  Center (x/y pair)
  ~469.9  Right flank (x/y pair)
  ~517.3  Left flank (x/y pair)
  ~547.0  Blue line right (x/y pair)
  ~594.4  Blue line center (x/y pair)
  ~644.4  Blue line left (x/y pair)
  ~691.9  Slapshot (x/y pair)
  ~744.8  Wrist shot (x/y pair)

Returns a list of dicts, one per player. Missing values are None
(rendered as em-dash in the PDF).
"""
from __future__ import annotations

import re
from collections import defaultdict
import pdfplumber
from ..pdf_nav import find_section_page, SHOTS_SECTION


# ── x-coordinate windows for each column ─────────────────────────────────────
# Each tuple is (x_min, x_max) for that column's data tokens
# Ranges are non-overlapping: each pair's shared boundary is (old_max + new_min) // 2
_COL_GOALS = (78, 100)
_COL_SHOTS = (105, 161)          # shots total/on-goal x/y pair
_COL_SHOTS_BLOCK = (161, 191)    # shots blocking (single int)
_COL_PP = (191, 241)             # power play x/y pair
_COL_SH = (241, 270)             # short-handed x/y pair
_COL_POSITIONAL = (270, 320)     # in positional attacks x/y pair
_COL_COUNTER = (320, 367)        # in counter-attacks x/y pair
_COL_SLOT = (367, 415)           # slot x/y pair
_COL_CENTER = (415, 465)         # center x/y pair
_COL_RIGHT_FLANK = (465, 514)    # right flank x/y pair
_COL_LEFT_FLANK = (514, 542)     # left flank x/y pair
_COL_BL_RIGHT = (542, 589)       # blue line right x/y pair
_COL_BL_CENTER = (589, 639)      # blue line center x/y pair
_COL_BL_LEFT = (639, 687)        # blue line left x/y pair
_COL_SLAPSHOT = (687, 740)       # slapshot x/y pair
_COL_WRISTSHOT = (740, 820)      # wrist shot x/y pair

# Jersey numbers: short digit tokens at left margin (~33)
_JERSEY_X_MAX = 40
_JERSEY_RE = re.compile(r"^\d{1,2}$")

# Player names: text at approximately x=43
_NAME_X_MIN = 40
_NAME_X_MAX = 80

# Ratio cell: "x/y" with slash separator
_RATIO_RE = re.compile(r"^(\d+)/(\d+)$")

# Percentage token (to skip)
_PCT_RE = re.compile(r"^\d+%$")

# Single int token
_INT_RE = re.compile(r"^\d+$")

# Em-dash token
_DASH = {"—", "-"}

# Columns to skip in header detection
_SKIP_NAMES = {"TOTAL", "SHOTS", "MATCH"}


def parse_shots(pdf: pdfplumber.PDF, our_team: str) -> list[dict]:
    """Return per-player shot data from the SHOTS page.

    Args:
        pdf:      Open pdfplumber PDF object.
        our_team: Full team name as it appears in the PDF header
                  (e.g. "HARVARD CRIMSON").

    Returns:
        list of dicts, one per player. Empty list if not found.
    """
    page_idx = find_section_page(pdf, SHOTS_SECTION, our_team)
    if page_idx is None:
        return []
    page = pdf.pages[page_idx]
    words = page.extract_words() or []
    return _extract_shot_rows(words)


def _in_col(x: float, col_range: tuple) -> bool:
    return col_range[0] <= x <= col_range[1]


def _extract_pair_from_row(row_words: list, col_range: tuple) -> tuple[int | None, int | None]:
    """Extract an x/y pair from words falling in col_range.

    Returns (x, y) where x=total, y=on_goal. Returns (None, None) if dash or absent.
    """
    for w in row_words:
        if not _in_col(w["x0"], col_range):
            continue
        txt = w["text"]
        if txt in _DASH:
            return None, None
        m = _RATIO_RE.match(txt)
        if m:
            return int(m.group(1)), int(m.group(2))
    return None, None


def _extract_int_from_row(row_words: list, col_range: tuple) -> int | None:
    """Extract a single integer from words falling in col_range.

    Returns None if dash or absent.
    """
    for w in row_words:
        if not _in_col(w["x0"], col_range):
            continue
        txt = w["text"]
        if txt in _DASH:
            return None
        if _INT_RE.match(txt):
            return int(txt)
    return None


def _empty_row() -> dict:
    row: dict = {"jersey_number": "", "player_name": ""}
    for k in ("goals", "shots_total", "shots_on_goal", "shots_blocked_defensively"):
        row[k] = None
    for total_key, on_goal_key in [
        ("pp_shots_total", "pp_shots_on_goal"),
        ("sh_shots_total", "sh_shots_on_goal"),
        ("positional_shots_total", "positional_shots_on_goal"),
        ("counter_shots_total", "counter_shots_on_goal"),
        ("slot_shots_total", "slot_shots_on_goal"),
        ("center_shots_total", "center_shots_on_goal"),
        ("right_flank_shots_total", "right_flank_shots_on_goal"),
        ("left_flank_shots_total", "left_flank_shots_on_goal"),
        ("blue_line_right_shots_total", "blue_line_right_shots_on_goal"),
        ("blue_line_center_shots_total", "blue_line_center_shots_on_goal"),
        ("blue_line_left_shots_total", "blue_line_left_shots_on_goal"),
        ("slapshot_total", "slapshot_on_goal"),
        ("wristshot_total", "wristshot_on_goal"),
    ]:
        row[total_key] = None
        row[on_goal_key] = None
    return row


def _extract_shot_rows(words: list) -> list[dict]:
    """Parse word-level bounding-box data into per-player shot records.

    Two layout variants exist in the fixture:
      Layout A: jersey + name + data all at the same rounded top (or with
                percentage tokens shifted ~0.5–1px below).
      Layout B: jersey on one line at top T, name + data on the line at T+1.
                (This happens when the name wraps to its own sub-line.)

    Strategy:
      1. Group words by rounded top into lines.
      2. Walk lines top-to-bottom.
      3. Lines whose leftmost word is a jersey number (x<40, digits) define a
         player row.
         - If name is also on this line → Layout A.
         - If next line starts with name (x~43) → Layout B; consume that line.
      4. Merge the next line if it starts with percentage tokens (shifted ~1px).
    """
    if not words:
        return []

    # Bucket words into lines by rounded top value
    lines: dict[int, list[dict]] = defaultdict(list)
    for w in words:
        key = round(w["top"])
        lines[key].append(w)

    sorted_tops = sorted(lines.keys())

    def get_row(top: int) -> list:
        return sorted(lines[top], key=lambda w: w["x0"])

    records: list[dict] = []
    consumed_tops: set = set()

    for idx, top in enumerate(sorted_tops):
        if top in consumed_tops:
            continue

        row_words = get_row(top)
        if not row_words:
            continue

        leftmost = row_words[0]
        left_x = leftmost["x0"]
        left_txt = leftmost["text"]

        # Only process rows that start with a jersey number at left margin
        if not (left_x <= _JERSEY_X_MAX and _JERSEY_RE.match(left_txt)):
            continue

        jersey = left_txt

        # Find name: check current line first
        player_name = ""
        for w in row_words[1:]:
            if _NAME_X_MIN <= w["x0"] <= _NAME_X_MAX and not _PCT_RE.match(w["text"]):
                player_name = w["text"]
                break

        # Layout B: name is on the next line
        combined_words = list(row_words)
        if not player_name and idx + 1 < len(sorted_tops):
            next_top = sorted_tops[idx + 1]
            next_words = get_row(next_top)
            if next_words:
                next_left = next_words[0]
                if _NAME_X_MIN <= next_left["x0"] <= _NAME_X_MAX and not _PCT_RE.match(next_left["text"]):
                    player_name = next_left["text"]
                    combined_words.extend(next_words)
                    consumed_tops.add(next_top)

        if not player_name:
            continue
        if player_name.upper() in _SKIP_NAMES:
            continue

        # Merge the next line if it only contains percentage tokens (shifted ~1px)
        # This handles the case where pct tokens are at a slightly different top
        # We look ahead for a non-jersey, non-name line within 2 tops
        for look_idx in range(idx + 1, min(idx + 3, len(sorted_tops))):
            look_top = sorted_tops[look_idx]
            if look_top in consumed_tops:
                continue
            look_words = get_row(look_top)
            if not look_words:
                continue
            look_left = look_words[0]
            # Only merge if the next line's leftmost is a pct token (not a jersey/name)
            if _PCT_RE.match(look_left["text"]):
                combined_words.extend(look_words)
                consumed_tops.add(look_top)
                break
            # Stop looking if we hit another jersey row
            if look_left["x0"] <= _JERSEY_X_MAX and _JERSEY_RE.match(look_left["text"]):
                break

        # Defensive sort to ensure combined_words is x0-sorted
        # (input sources are individually sorted, but merged fragment may not be globally sorted)
        combined_words.sort(key=lambda w: w["x0"])

        row = _empty_row()
        row["jersey_number"] = jersey
        row["player_name"] = player_name

        # Extract Goals (single int or dash)
        row["goals"] = _extract_int_from_row(combined_words, _COL_GOALS)

        # Extract Shots total/on-goal (x/y pair)
        shots_total, shots_on_goal = _extract_pair_from_row(combined_words, _COL_SHOTS)
        row["shots_total"] = shots_total
        row["shots_on_goal"] = shots_on_goal

        # Extract Shots blocking (single int or dash)
        row["shots_blocked_defensively"] = _extract_int_from_row(combined_words, _COL_SHOTS_BLOCK)

        # Extract all x/y pair columns
        pp_t, pp_og = _extract_pair_from_row(combined_words, _COL_PP)
        row["pp_shots_total"] = pp_t
        row["pp_shots_on_goal"] = pp_og

        sh_t, sh_og = _extract_pair_from_row(combined_words, _COL_SH)
        row["sh_shots_total"] = sh_t
        row["sh_shots_on_goal"] = sh_og

        pos_t, pos_og = _extract_pair_from_row(combined_words, _COL_POSITIONAL)
        row["positional_shots_total"] = pos_t
        row["positional_shots_on_goal"] = pos_og

        ctr_t, ctr_og = _extract_pair_from_row(combined_words, _COL_COUNTER)
        row["counter_shots_total"] = ctr_t
        row["counter_shots_on_goal"] = ctr_og

        slot_t, slot_og = _extract_pair_from_row(combined_words, _COL_SLOT)
        row["slot_shots_total"] = slot_t
        row["slot_shots_on_goal"] = slot_og

        cen_t, cen_og = _extract_pair_from_row(combined_words, _COL_CENTER)
        row["center_shots_total"] = cen_t
        row["center_shots_on_goal"] = cen_og

        rf_t, rf_og = _extract_pair_from_row(combined_words, _COL_RIGHT_FLANK)
        row["right_flank_shots_total"] = rf_t
        row["right_flank_shots_on_goal"] = rf_og

        lf_t, lf_og = _extract_pair_from_row(combined_words, _COL_LEFT_FLANK)
        row["left_flank_shots_total"] = lf_t
        row["left_flank_shots_on_goal"] = lf_og

        blr_t, blr_og = _extract_pair_from_row(combined_words, _COL_BL_RIGHT)
        row["blue_line_right_shots_total"] = blr_t
        row["blue_line_right_shots_on_goal"] = blr_og

        blc_t, blc_og = _extract_pair_from_row(combined_words, _COL_BL_CENTER)
        row["blue_line_center_shots_total"] = blc_t
        row["blue_line_center_shots_on_goal"] = blc_og

        bll_t, bll_og = _extract_pair_from_row(combined_words, _COL_BL_LEFT)
        row["blue_line_left_shots_total"] = bll_t
        row["blue_line_left_shots_on_goal"] = bll_og

        sl_t, sl_og = _extract_pair_from_row(combined_words, _COL_SLAPSHOT)
        row["slapshot_total"] = sl_t
        row["slapshot_on_goal"] = sl_og

        ws_t, ws_og = _extract_pair_from_row(combined_words, _COL_WRISTSHOT)
        row["wristshot_total"] = ws_t
        row["wristshot_on_goal"] = ws_og

        records.append(row)

    return records
