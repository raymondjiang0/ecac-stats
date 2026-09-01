"""Parser for InStat's PLAYERS' STATS page (P3 for visitor, P11 for home).

Layout: 16-row table (one per player) with multi-valued cells. Each row
carries the player's jersey and name plus performance stats. The page text
is extracted in two sections:

Section 1 (Main statistics): lines matching "<jersey> <LastName> <InStatIdx>
<goals> <assists> <points> <+/-> <TOI> <shifts> <PPtime> <SHTtime>
<penalty_time> <shots/sog> [pct] <pp_shots/pp_sog> <corsi+> <corsi->
<corsi_total> <hits_del> <hits_recv> [<fo/won> [pct] <fo_dz> <fo_oz>]
<shots_blocking>"

Section 2 (Turnovers/Entries): each line repeats the jersey+name 3 times —
once for puck-battle stats (ignored), once for puck losses/recoveries, and
once for zone entries.

Returns a list of dicts, one per player, each with a jersey/name and any
PlayerGameStatsInStat main fields the parser could extract.
"""
from typing import Optional
import re
import pdfplumber
from ..pdf_nav import find_section_page, PLAYERS_STATS_SECTION
from .team_stats import _parse_int  # reuse int-with-em-dash helper

# Regex to identify player data lines in the main stats section:
# Starts with 1-2 digit jersey number, space, Last Name (capitalized), space, number (InStat index)
_MAIN_ROW_RE = re.compile(r"^\d{1,2}\s+[A-Z][a-z]+\s+\d+\s")


def parse_players_main(pdf: pdfplumber.PDF, our_team: str) -> list[dict]:
    page_idx = find_section_page(pdf, PLAYERS_STATS_SECTION, our_team)
    if page_idx is None:
        return []
    page = pdf.pages[page_idx]
    text = page.extract_text() or ""
    return _extract_player_rows(text)


def _extract_player_rows(text: str) -> list[dict]:
    """Walk page text lines and produce one dict per player.

    The text is split into two sections:
    - Main stats (Section 1): each data line starts with jersey + name + InStat index
    - Turnovers/entries (Section 2): each data line repeats jersey+name 3 times

    We parse both sections and merge by jersey number.
    """
    lines = text.splitlines()

    # --- Split into two sections ---
    # Section 2 starts at the line containing 'Challenges' or 'Turnovers'
    section2_start = None
    for i, line in enumerate(lines):
        if "Challenges" in line or "Turnovers" in line:
            section2_start = i
            break

    section1_lines = lines[:section2_start] if section2_start else lines
    section2_lines = lines[section2_start:] if section2_start else []

    # --- Parse Section 1 ---
    main_rows: dict[str, dict] = {}  # jersey -> partial dict
    for line in section1_lines:
        row = _parse_main_stats_line(line)
        if row:
            main_rows[row["jersey_number"]] = row

    # --- Parse Section 2 ---
    secondary_rows: dict[str, dict] = {}  # jersey -> partial dict
    for line in section2_lines:
        row = _parse_secondary_line(line)
        if row:
            secondary_rows[row["jersey_number"]] = row

    # --- Merge ---
    result = []
    for jersey, main in main_rows.items():
        merged = dict(main)
        if jersey in secondary_rows:
            sec = secondary_rows[jersey]
            for k, v in sec.items():
                if k not in merged:
                    merged[k] = v
        result.append(merged)

    return result


def _parse_main_stats_line(line: str) -> Optional[dict]:
    """Parse a single main-stats row.

    Positions (all relative to the line's token list):
      0: jersey_number
      1: player_name (last name)
      2: InStat Index (skip)
      3: goals (skip)
      4: assists (skip)
      5: points (skip)
      6: +/- (skip)
      TOI at the first MM:SS token starting from index 2
      TOI+1: shifts (skip)
      TOI+2: PP time (skip)
      TOI+3: SH time (skip)
      TOI+4: penalty time
      TOI+5: shots/shots_on_goal OR — (if x/y, next token is pct%)
      next: pp_shots/pp_shots_on_goal OR — (no pct follows)
      +3: corsi+, corsi-, corsi_total
      +2: hits_delivered, hits_received
      (variable faceoff columns follow, not extracted here)
    """
    tokens = line.split()
    if len(tokens) < 10:
        return None

    # Must start with jersey (digits) and name (capitalized word)
    if not re.match(r"^\d{1,2}$", tokens[0]):
        return None
    if not re.match(r"^[A-Z][a-z]", tokens[1]):
        return None
    # Third token must be InStat index (integer)
    if not re.match(r"^\d+$", tokens[2]):
        return None

    jersey = tokens[0]
    name = tokens[1]

    # Find TOI: first MM:SS token at index 2+
    toi_idx = None
    for i, t in enumerate(tokens[2:], start=2):
        if re.match(r"^\d+:\d{2}$", t):
            toi_idx = i
            break
    if toi_idx is None:
        return None

    penalty_idx = toi_idx + 4
    pos = penalty_idx + 1  # start parsing after penalty time

    shots = shots_on_goal = pp_shots = pp_shots_on_goal = None

    # Shots / shots on goal column: x/y or —
    # If x/y present, a percentage token follows
    if pos < len(tokens):
        tok = tokens[pos]
        if "/" in tok and not tok.startswith("-"):
            parts = tok.split("/")
            try:
                shots = int(parts[0])
                shots_on_goal = int(parts[1])
            except (ValueError, IndexError):
                pass
            pos += 2  # skip x/y and pct%
        else:
            pos += 1  # skip — (no pct follows)

    # Power play shots column: x/y or — (no pct follows in either case)
    if pos < len(tokens):
        tok = tokens[pos]
        if "/" in tok and not tok.startswith("-"):
            parts = tok.split("/")
            try:
                pp_shots = int(parts[0])
                pp_shots_on_goal = int(parts[1])
            except (ValueError, IndexError):
                pass
        pos += 1  # advance past pp column

    # Corsi: 3 tokens (corsi+, corsi-, corsi_total)
    corsi_plus = corsi_minus = None
    if pos + 2 < len(tokens):
        corsi_plus = _parse_int(tokens[pos])
        corsi_minus = _parse_int(tokens[pos + 1])
        # tokens[pos+2] = corsi total (skip)
        pos += 3

    # Hits: 2 tokens (hits_delivered, hits_received)
    hits_delivered = hits_received = None
    if pos + 1 < len(tokens):
        hits_delivered = _parse_int(tokens[pos])
        hits_received = _parse_int(tokens[pos + 1])

    return {
        "jersey_number": jersey,
        "player_name": name,
        "shots": shots,
        "shots_on_goal": shots_on_goal,
        "blocked_shots": None,  # not on this page
        "pp_shots": pp_shots,
        "pp_shots_on_goal": pp_shots_on_goal,
        "corsi_plus": corsi_plus,
        "corsi_minus": corsi_minus,
        "hits_delivered": hits_delivered,
        "hits_received": hits_received,
    }


def _parse_secondary_line(line: str) -> Optional[dict]:
    """Parse a second-section line (puck losses/recoveries + zone entries).

    Each line contains jersey+name repeated 3 times:
      Group 1: puck battle stats (ignored)
      Group 2: puck_losses, puck_losses_dz, puck_recoveries, puck_recoveries_oz
      Group 3: entries_total (skip), entries_pass [pct], entries_stick [pct],
               entries_dump [pct]

    Pct tokens (ending with %) are optional — they only appear when the
    preceding stat value is non-dash. We skip them dynamically.
    """
    # Find all occurrences of "jersey LastName" in the line
    pattern = r"\b(\d{1,2})\s+([A-Za-z]+)"
    matches = list(re.finditer(pattern, line))

    if len(matches) < 3:
        return None

    jersey = matches[0].group(1)
    # Slice between matches to get each group's data
    group2_str = line[matches[1].end() : matches[2].start()].strip()
    group3_str = line[matches[2].end() :].strip()

    puck_losses = puck_losses_dz = puck_recoveries = puck_recoveries_oz = None
    g2_tokens = group2_str.split()
    if len(g2_tokens) >= 1:
        puck_losses = _parse_int(g2_tokens[0])
    if len(g2_tokens) >= 2:
        puck_losses_dz = _parse_int(g2_tokens[1])
    if len(g2_tokens) >= 3:
        puck_recoveries = _parse_int(g2_tokens[2])
    if len(g2_tokens) >= 4:
        puck_recoveries_oz = _parse_int(g2_tokens[3])

    entries_pass = entries_stick = entries_dump = None
    g3_tokens = group3_str.split()
    # g3_tokens[0] = total entries (not stored); skip it
    entries_pass, entries_stick, entries_dump = _parse_entries_tokens(g3_tokens[1:])

    return {
        "jersey_number": jersey,
        "puck_losses": puck_losses,
        "puck_losses_dz": puck_losses_dz,
        "puck_recoveries": puck_recoveries,
        "puck_recoveries_oz": puck_recoveries_oz,
        "entries_pass": entries_pass,
        "entries_stick": entries_stick,
        "entries_dump": entries_dump,
    }


def _parse_entries_tokens(tokens: list[str]) -> tuple[Optional[int], Optional[int], Optional[int]]:
    """Parse entries_pass, entries_stick, entries_dump from a token list.

    Percentage tokens (ending in %) are present only after non-dash values;
    we skip them dynamically.

    tokens format (conceptually):
      entries_pass [pct%] entries_stick [pct%] entries_dump [pct%]
    """
    idx = 0
    results = []

    for _ in range(3):  # parse up to 3 entry type values
        if idx >= len(tokens):
            results.append(None)
            continue
        val = tokens[idx]
        idx += 1
        if val == "—":
            results.append(None)
            # No pct follows a dash
        else:
            try:
                results.append(int(val))
            except ValueError:
                results.append(None)
            # Skip pct token if present
            if idx < len(tokens) and tokens[idx].endswith("%"):
                idx += 1

    while len(results) < 3:
        results.append(None)

    return results[0], results[1], results[2]
