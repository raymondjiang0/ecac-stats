"""Parser for InStat's CHALLENGES page (P7/15).

Layout: per-player puck-battle counts by zone (DZ / OZ / NZ). Cells report
'total/won' pairs (e.g. '6/2') followed by a win-percentage token (e.g. '33%').
An em-dash ('—') indicates zero challenges in that zone.

Column x-coordinate anchors (from fixture inspection at
backend/tests/fixtures/instat_sample.pdf):
  ~107  Challenges (overall total)
  ~160  Defensive zone aggregate
  ~414  Offensive zone aggregate
  ~659  Neutral zone aggregate

Intermediate sub-zone columns (~214, ~261, ~311, ~361 for DZ;
~465, ~507, ~556, ~609 for OZ) are ignored — only the aggregate columns are
extracted.

Two row layouts appear in the fixture:
  Layout A: jersey and name on the same text line; ratio values also on same line.
  Layout B: name (with ratio values) on one line; jersey (with %-only values)
            on the next line at a slightly different vertical position.

Returns list of dicts with pb_* fields matching PlayerGameStatsInStat.
Note: cell format is 'total/won', so pb_total = first number, pb_won = second.
"""
from __future__ import annotations

import re
from collections import defaultdict
import pdfplumber
from ..pdf_nav import find_section_page, CHALLENGES_SECTION


# ── x-coordinate windows for each aggregate zone column ──────────────────────
_COL_DZ_X = (148, 200)           # defensive zone (~160)
_COL_OZ_X = (400, 455)           # offensive zone (~414)
_COL_NZ_X = (645, 700)           # neutral zone (~659)

# Jersey numbers: short digit tokens at left margin (~33)
_JERSEY_X_MAX = 40
_JERSEY_RE = re.compile(r"^\d{1,2}$")

# Player names: text at approximately x=43 (slightly indented from jersey)
_NAME_X_MIN = 40
_NAME_X_MAX = 75

# Ratio cell: "total/won" with slash separator
_RATIO_RE = re.compile(r"^(\d+)/(\d+)$")

# Percentage token (to skip)
_PCT_RE = re.compile(r"^\d+%$")


def parse_challenges(pdf: pdfplumber.PDF, our_team: str) -> list[dict]:
    """Return per-player puck-battle zone counts from the CHALLENGES page.

    Args:
        pdf:      Open pdfplumber PDF object.
        our_team: Full team name as it appears in the PDF header
                  (e.g. "HARVARD CRIMSON").

    Returns:
        list of dicts, one per player:
            jersey_number : str
            player_name   : str  (last name only)
            pb_won_dz     : int | None
            pb_total_dz   : int | None
            pb_won_oz     : int | None
            pb_total_oz   : int | None
            pb_won_nz     : int | None
            pb_total_nz   : int | None
        Empty list if the section cannot be located for the given team.
    """
    page_idx = find_section_page(pdf, CHALLENGES_SECTION, our_team)
    if page_idx is None:
        return []
    page = pdf.pages[page_idx]
    words = page.extract_words() or []
    return _extract_challenge_rows(words)


def _parse_won_total(cell: str) -> tuple[int | None, int | None]:
    """Parse 'total/won' or 'total—won' or '—' cells.

    The InStat format places total first and won second (e.g. '6/2' means
    6 total, 2 won). Returns (won, total). Either or both may be None.

    Handles slash ('/'), em-dash ('—'), and hyphen ('-') separators.
    A bare '—' means zero challenges → returns (None, None).
    """
    if not cell:
        return None, None
    cell = cell.strip()
    if cell in ("—", "-", ""):
        return None, None
    # Match "total/won" or "total—won" or "total-won"
    m = re.match(r"^(\d+)\s*[/\u2014-]\s*(\d+)$", cell)
    if not m:
        return None, None
    total = int(m.group(1))
    won = int(m.group(2))
    # Enforce won ≤ total invariant; drop both if violated
    if won > total:
        return None, None
    return won, total


def _in_col(x: float, col_range: tuple) -> bool:
    return col_range[0] <= x <= col_range[1]


def _extract_zone_values(row_words: list) -> "tuple[str, str, str]":
    """Scan words in a row and return (dz_cell, oz_cell, nz_cell).

    Only picks up ratio tokens (X/Y) falling within the DZ, OZ, NZ x-windows.
    Returns '—' for zones not found.
    """
    dz_cell = "—"
    oz_cell = "—"
    nz_cell = "—"
    for w in row_words:
        txt = w["text"]
        x = w["x0"]
        if _RATIO_RE.match(txt):
            if _in_col(x, _COL_DZ_X):
                dz_cell = txt
            elif _in_col(x, _COL_OZ_X):
                oz_cell = txt
            elif _in_col(x, _COL_NZ_X):
                nz_cell = txt
    return dz_cell, oz_cell, nz_cell


def _extract_challenge_rows(words: list) -> list[dict]:
    """Parse word-level bounding-box data into per-player challenge records.

    Handles two layout variants:
      Layout A: jersey + name + ratio values all on the same text line.
                The leftmost token is the jersey number at x < 40.
      Layout B: name + ratio values on one line (leftmost at x ~43),
                jersey number on the next line (leftmost at x ~33, digits only).

    Strategy:
      1. Group words by rounded vertical position into text lines.
      2. Walk lines in top-to-bottom order.
      3. For Layout A: jersey row → collect name + zone values from the same line.
      4. For Layout B: name row (no jersey at left margin) → collect zone values,
         then read jersey from the immediately following line.
    """
    if not words:
        return []

    # Step 1: bucket words into lines by rounded top value
    lines: dict[int, list[dict]] = defaultdict(list)
    for w in words:
        key = round(w["top"])
        lines[key].append(w)

    sorted_tops = sorted(lines.keys())

    # Build a quick index: top → sorted word list
    def get_row(top: int) -> list:
        return sorted(lines[top], key=lambda w: w["x0"])

    records: list[dict] = []
    consumed_tops: set = set()  # tops already absorbed as jersey rows in Layout B

    for idx, top in enumerate(sorted_tops):
        if top in consumed_tops:
            continue

        row_words = get_row(top)
        if not row_words:
            continue

        leftmost = row_words[0]
        left_x = leftmost["x0"]
        left_txt = leftmost["text"]

        # ── Layout A: jersey is the leftmost token ──────────────────────────
        if left_x <= _JERSEY_X_MAX and _JERSEY_RE.match(left_txt):
            jersey = left_txt
            # Find name: next token in the name x-band
            player_name = ""
            for w in row_words[1:]:
                if _NAME_X_MIN <= w["x0"] <= _NAME_X_MAX and not _PCT_RE.match(w["text"]):
                    player_name = w["text"]
                    break
            if not player_name:
                continue
            if player_name.upper() in ("TOTAL", "CHALLENGES"):
                continue
            dz, oz, nz = _extract_zone_values(row_words)
            _append_record(records, jersey, player_name, dz, oz, nz)
            continue

        # ── Layout B: name + data on this line; jersey on next line ────────
        # Detect: leftmost is in name x-band, is not a digit, not a percent
        if (_NAME_X_MIN <= left_x <= _NAME_X_MAX
                and not _JERSEY_RE.match(left_txt)
                and not _PCT_RE.match(left_txt)
                and left_txt.upper() not in ("TOTAL", "CHALLENGES", "MATCH")):
            player_name = left_txt
            dz, oz, nz = _extract_zone_values(row_words)

            # Look for jersey on the immediately following line
            jersey = None
            if idx + 1 < len(sorted_tops):
                next_top = sorted_tops[idx + 1]
                next_words = get_row(next_top)
                if next_words:
                    nxt_left = next_words[0]
                    if nxt_left["x0"] <= _JERSEY_X_MAX and _JERSEY_RE.match(nxt_left["text"]):
                        jersey = nxt_left["text"]
                        consumed_tops.add(next_top)

            if not jersey:
                continue  # can't identify jersey; skip
            _append_record(records, jersey, player_name, dz, oz, nz)

    return records


def _append_record(
    records: list,
    jersey: str,
    player_name: str,
    dz_cell: str,
    oz_cell: str,
    nz_cell: str,
) -> None:
    pb_won_dz, pb_total_dz = _parse_won_total(dz_cell)
    pb_won_oz, pb_total_oz = _parse_won_total(oz_cell)
    pb_won_nz, pb_total_nz = _parse_won_total(nz_cell)
    records.append({
        "jersey_number": jersey,
        "player_name": player_name,
        "pb_won_dz": pb_won_dz,
        "pb_total_dz": pb_total_dz,
        "pb_won_oz": pb_won_oz,
        "pb_total_oz": pb_total_oz,
        "pb_won_nz": pb_won_nz,
        "pb_total_nz": pb_total_nz,
    })
