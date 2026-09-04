"""Parser for InStat's GAME TIME DISTRIBUTION page (P5/13).

Layout discovery (fixture page 13, 0-indexed page 12):
  The page shows per-player ice time split across three columns. Inspecting
  word bounding boxes reveals the three time columns land at approximately:
    - x ~297  (column A)
    - x ~544  (column B)
    - x ~791  (column C)

  The column header labels (`SH PP SH SH PP PP SH PP`) represent the
  strength state at which each goal was scored (from this team's perspective),
  NOT the strength state for each time column.  Summing per-column times over
  all skaters yields ~97-98 total skater-minutes per column, consistent with a
  20-minute period in which 5 skaters share ice time — confirming the three
  columns are Period 1, Period 2, and Period 3 (or first three OT periods).

  Consequence: per-strength-state (5v5/PP/SH) totals are NOT directly
  extractable from this page.  This parser therefore:
    - Sets toi_5v5_seconds = sum of all period times (total TOI proxy).
    - Sets toi_pp_seconds  = None  (unavailable from this layout).
    - Sets toi_sh_seconds  = None  (unavailable from this layout).

  Row structure (from extracted text):
    Line N+0: jersey number (digits only, left margin)
    Line N+1: "X shifts MM:SS  Y shifts MM:SS  Z shifts MM:SS"  (time data)
              OR partial — when the first-column time wraps, it appears at the
              start of Line N+2 (the player name line).
    Line N+2: player last name (possibly prefixed by a wrapped time token)

  Word extraction is used instead of table extraction because pdfplumber's
  table parser produces a very sparse 76-column matrix for this page, making
  column alignment unreliable.
"""
import re
from typing import Optional
import pdfplumber
from ..pdf_nav import find_section_page, GAME_TIME_SECTION
from .team_stats import _parse_time_to_seconds

# X-coordinate boundaries for the three time columns (centre ± 60 pts)
_COL_A_X = (240, 360)   # ~297
_COL_B_X = (490, 605)   # ~544
_COL_C_X = (745, 830)   # ~791

# Jersey numbers are short all-digit tokens at the left margin
_JERSEY_X_MAX = 80
_JERSEY_RE = re.compile(r"^\d{1,2}$")

# Time tokens like "05:33" or "1:23:45"
_TIME_RE = re.compile(r"^\d+:\d{2}(?::\d{2})?$")

# Section label lines to skip
_SKIP_RE = re.compile(r"^(FIRST|SECOND|THIRD|FOURTH|OTHER)\s+", re.IGNORECASE)

# Left-margin X threshold for player names / jersey numbers
_LEFT_MARGIN_X_MAX = 90


def parse_time_distribution(pdf: pdfplumber.PDF, our_team: str) -> list[dict]:
    """Return per-player TOI data from the GAME TIME DISTRIBUTION page.

    Args:
        pdf:      Open pdfplumber PDF object.
        our_team: Full team name as it appears in the PDF header
                  (e.g. "HARVARD CRIMSON").

    Returns:
        list of dicts, one per player:
            jersey_number  : str
            player_name    : str   (last name only)
            toi_5v5_seconds: int | None   (total TOI across all periods; PP/SH not
                                    separately available from this page layout)
            toi_pp_seconds : None  (unavailable — see module docstring)
            toi_sh_seconds : None  (unavailable — see module docstring)
        Empty list if the section cannot be located for the given team.
    """
    page_idx = find_section_page(pdf, GAME_TIME_SECTION, our_team)
    if page_idx is None:
        return []
    page = pdf.pages[page_idx]
    words = page.extract_words() or []
    return _extract_time_rows(words)


def _in_col(x: float, col_range: tuple) -> bool:
    return col_range[0] <= x <= col_range[1]


def _extract_time_rows(words: list) -> list[dict]:
    """Parse word-level bounding-box data into per-player TOI records.

    Strategy:
      1. Group words by their rounded vertical position (top) into text lines.
      2. Walk lines in order. When a line consists solely of a jersey-number
         token at the left margin, start a new player record.
      3. Collect time tokens from the subsequent 1-3 lines by matching their
         x-coordinates to one of the three period columns (cap at 4 lines total
         to handle wrapped time tokens and defense against layout drift).
      4. The player name follows the jersey number line (possibly on the same
         line as a wrapped time token).
    """
    if not words:
        return []

    # --- Step 1: bucket words into lines by rounded top value ---
    lines: dict[int, list[dict]] = {}
    for w in words:
        key = round(w["top"])
        lines.setdefault(key, []).append(w)

    sorted_tops = sorted(lines.keys())

    # --- Step 2-4: walk lines and build records ---
    records: list[dict] = []
    # NOTE: assumes the InStat page header is exactly 2 lines (matches the
    # fixture layout). If InStat changes their header size, jersey numbers
    # appearing in header lines could be misprocessed or dropped.
    skip_tops = set()  # header/meta tops to ignore

    # Mark the first two lines (page header) as skip
    for t in sorted_tops[:2]:
        skip_tops.add(t)

    i = 0
    while i < len(sorted_tops):
        top = sorted_tops[i]
        if top in skip_tops:
            i += 1
            continue

        line_words = sorted(lines[top], key=lambda w: w["x0"])
        tokens = [w["text"] for w in line_words]
        x_positions = [w["x0"] for w in line_words]

        # Skip section-label lines (FIRST LINE, SECOND LINE, etc.)
        joined = " ".join(tokens)
        if _SKIP_RE.match(joined):
            i += 1
            continue

        # Detect jersey-number line: single digit/2-digit token at left margin
        if (len(line_words) == 1
                and _JERSEY_RE.match(tokens[0])
                and x_positions[0] <= _JERSEY_X_MAX):

            jersey = tokens[0]
            times: dict[str, Optional[int]] = {"A": None, "B": None, "C": None}
            player_name: Optional[str] = None

            # Scan the next 3 lines for time tokens and the player name
            j = i + 1
            name_found = False
            lines_scanned = 0
            while j < len(sorted_tops) and lines_scanned < 4:
                next_top = sorted_tops[j]
                next_words = sorted(lines[next_top], key=lambda w: w["x0"])

                for w in next_words:
                    txt = w["text"]
                    x = w["x0"]

                    if _TIME_RE.match(txt):
                        if _in_col(x, _COL_A_X):
                            times["A"] = _parse_time_to_seconds(txt)
                        elif _in_col(x, _COL_B_X):
                            times["B"] = _parse_time_to_seconds(txt)
                        elif _in_col(x, _COL_C_X):
                            times["C"] = _parse_time_to_seconds(txt)
                        # else: time in an unexpected column; ignore

                    elif x <= _LEFT_MARGIN_X_MAX and not _TIME_RE.match(txt):
                        # Left-margin non-time, non-jersey token → player name
                        if not name_found and not _JERSEY_RE.match(txt):
                            player_name = txt
                            name_found = True

                # Stop scanning once we hit the next jersey-number line
                nxt_tokens = [w["text"] for w in next_words]
                nxt_xs = [w["x0"] for w in next_words]
                if (len(next_words) == 1
                        and _JERSEY_RE.match(nxt_tokens[0])
                        and nxt_xs[0] <= _JERSEY_X_MAX):
                    break

                j += 1
                lines_scanned += 1

            if player_name is None:
                i += 1
                continue  # couldn't identify player name; skip

            # Sum non-None period times as total TOI
            period_times = [t for t in times.values() if t is not None]
            total_toi = sum(period_times) if period_times else None

            records.append({
                "jersey_number": jersey,
                "player_name": player_name,
                "toi_5v5_seconds": total_toi,
                "toi_pp_seconds": None,
                "toi_sh_seconds": None,
            })

        i += 1

    return records
