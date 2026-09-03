"""Parser for InStat's HITS DISTRIBUTION page (P9/17).

Layout: NxN matrix with players as both rows and columns. Each cell is
'delivered—received' (from row's perspective vs. column player), or '—'
for no interaction. Returns one dict per non-empty from/to pair.

Text layout (from extract_text()):
  Line 0: date / score header
  Line 1: section header with team name and page number
  Line 2: "Hits"
  Line 3: column jersey numbers (space-separated), ending with "TOTAL"
  Line 4: column last names (space-separated)
  Data rows (groups of 3 lines per player):
    - jersey number
    - space-separated cell values ("—" or "N—M"), ending with TOTAL cell
    - last name
  Final line: "TOTAL ..."
"""
import re
import pdfplumber
from ..pdf_nav import find_section_page, HITS_DISTRIBUTION_SECTION
from .challenges import _parse_won_total  # 'a—b' → (a, b) parser

_JERSEY_RE = re.compile(r"^\d{1,2}$")


def parse_hit_matrix(pdf: pdfplumber.PDF, our_team: str) -> list[dict]:
    """Return non-empty from→to hit pairs from the HITS DISTRIBUTION page.

    Args:
        pdf:      Open pdfplumber PDF object.
        our_team: Full team name as it appears in the PDF header
                  (e.g. "HARVARD CRIMSON").

    Returns:
        list of dicts, one per non-empty from/to pair:
            from_jersey : str
            from_name   : str  (last name)
            to_jersey   : str
            to_name     : str  (last name)
            delivered   : int
            received    : int
        Empty list if the section cannot be located for the given team.
        Pairs where both delivered and received are 0 are omitted.
    """
    page_idx = find_section_page(pdf, HITS_DISTRIBUTION_SECTION, our_team)
    if page_idx is None:
        return []
    page = pdf.pages[page_idx]
    text = page.extract_text() or ""
    return _extract_hit_pairs(text)


def _extract_hit_pairs(text: str) -> list[dict]:
    """Walk the text-extracted matrix and yield one dict per non-empty cell.

    Parses the jersey-numbers header row, the names header row, then iterates
    through player data rows (each is a 3-line group: jersey, cells, name).
    Uses _parse_won_total to parse each 'delivered—received' cell.
    Skips cells that parse to (None, None) (i.e. bare '—') or (0, 0).
    """
    lines = text.splitlines()

    # Find header line with jersey numbers (columns)
    # It starts with a digit and contains "TOTAL"
    col_jerseys: list[str] = []
    col_names: list[str] = []
    header_idx = -1

    for i, line in enumerate(lines):
        stripped = line.strip()
        tokens = stripped.split()
        # The jersey header line: all tokens are digits or "TOTAL"
        if (tokens and tokens[0].isdigit()
                and "TOTAL" in tokens
                and all(t.isdigit() or t == "TOTAL" for t in tokens)):
            col_jerseys = [t for t in tokens if t != "TOTAL"]
            header_idx = i
            break

    if header_idx < 0 or not col_jerseys:
        return []

    # Next line after jersey header is the names header
    names_line_idx = header_idx + 1
    if names_line_idx >= len(lines):
        return []
    col_names = lines[names_line_idx].strip().split()

    if len(col_jerseys) != len(col_names):
        # Mismatch; can't align columns
        return []

    n_cols = len(col_jerseys)

    # Data rows follow: groups of 3 lines per player
    #   line[i+0]: jersey number (a 1-2 digit string)
    #   line[i+1]: cell values (space-separated, N+1 tokens: N cells + TOTAL)
    #   line[i+2]: last name
    # We continue until we hit the TOTAL summary line
    data_start = names_line_idx + 1
    remaining = lines[data_start:]

    players: list[tuple[str, str]] = []  # (jersey, name) for each row player
    cell_rows: list[list[str]] = []       # parallel list of cell-value lists

    i = 0
    while i < len(remaining):
        line = remaining[i].strip()

        # Stop at the TOTAL summary line
        if line.upper().startswith("TOTAL"):
            break

        # Detect jersey line: 1-2 digit integer
        if _JERSEY_RE.match(line):
            jersey = line
            # Next line should be cell values
            if i + 1 >= len(remaining):
                break
            cells_line = remaining[i + 1].strip()
            cells_tokens = cells_line.split()
            # Next line after that should be the player name
            if i + 2 >= len(remaining):
                break
            name_line = remaining[i + 2].strip()

            # Validate: cells_tokens should have n_cols + 1 tokens (cells + TOTAL)
            # or n_cols tokens (if TOTAL is missing). Accept either.
            if len(cells_tokens) >= n_cols:
                cells = cells_tokens[:n_cols]  # drop the TOTAL cell
                players.append((jersey, name_line))
                cell_rows.append(cells)
            i += 3
        else:
            i += 1

    if not players or not cell_rows:
        return []

    # Build output: for each row player × each col player, emit if non-empty
    results: list[dict] = []
    for row_idx, (from_jersey, from_name) in enumerate(players):
        for col_idx, cell in enumerate(cell_rows[row_idx]):
            delivered, received = _parse_won_total(cell)
            # Skip empty cells (None) and zero-zero interactions
            if delivered is None and received is None:
                continue
            d = delivered if delivered is not None else 0
            r = received if received is not None else 0
            if d == 0 and r == 0:
                continue
            results.append({
                "from_jersey": from_jersey,
                "from_name": from_name,
                "to_jersey": col_jerseys[col_idx],
                "to_name": col_names[col_idx],
                "delivered": d,
                "received": r,
            })

    return results
