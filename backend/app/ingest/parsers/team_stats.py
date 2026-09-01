"""Parser for InStat's TEAMS STATS 2 page (P2).

Layout: columns alternate visiting-team, our-team ("PT HC PT HC ..."). Row
labels identify each stat. This parser reads the header row to locate our
team's columns, then walks stat rows and picks the matching column values.

Returns a dict of TeamGameStatsInStat-compatible field values (int/float/None).

P2 (page index 1) layout observed from fixture (Princeton vs Harvard):
  Header row: "PT HC PT HC PT HC PT HC"  (PT=visiting, HC=home/our team)
  Values for our team (HC) are always the second value in each PT/HC pair.

Key row patterns (regex-matched against each line of extracted text):
  - "Power play minutes played <PT_time> <HC_time>"
  - "Out of which in offensive zone <PT_time> <HC_time>"
  - "Power play <PT_x/y/z> <HC_x/y/z> ..."   (shots = first slash-group)
  - "Opp breakouts <PT_n> <HC_n>"
  - "Breakouts <PT_n> <HC_n>"                 (in SH section)
  - "Puck possessions <PT_time> <HC_time>"    (total possession)
  - "Offensive zone <PT_time> <PT_pct>% <HC_time> <HC_pct>%"
  - "Shots from a scoring chance area <PT_x/y/z> <HC_x/y/z>"
"""
from typing import Optional
import re
import pdfplumber
from ..pdf_nav import find_section_page, TEAMS_STATS_SECTION


def parse_team_stats(pdf: pdfplumber.PDF, our_team: str) -> dict:
    page_idx = find_section_page(pdf, TEAMS_STATS_SECTION, our_team)
    result = {
        "pp_shots": None,
        "pp_time_seconds_in_oz": None,
        "pp_time_seconds_total": None,
        "pk_opp_breakouts": None,
        "pp_opp_breakouts_allowed": None,
        "puck_possession_seconds_total": None,
        "oz_possession_seconds": None,
        "oz_possession_pct": None,
        "scoring_chance_shots": None,
        "scoring_chance_shots_on_goal": None,
    }
    if page_idx is None:
        return result

    page = pdf.pages[page_idx]
    text = page.extract_text() or ""
    _populate_from_page(result, text, our_team)
    return result


def _populate_from_page(
    result: dict, text: str, our_team: str
) -> None:
    """Walk the page's text lines filling result dict fields.

    Column ordering on P2: visiting-team (PT) values come first, our-team
    (HC) values come second within each section's pair. We identify which
    team is 'ours' via the header row ("PT HC ...") and _team_abbrev, but
    because the PDF consistently places the home team second, we simply
    take the second value of each matched pair.

    To distinguish the "Breakouts" row in the short-handed section from
    other breakouts rows, we track whether we've passed the "Short-handed
    play" header line.
    """
    our_abbrev = _team_abbrev(our_team)
    lines = text.splitlines()

    # Determine column index (0=first/visiting, 1=second/our) by finding
    # the header row that begins with a 2-letter team abbreviation pair
    # (e.g. "PT HC PT HC ...") and locating our team's abbreviation in it.
    our_col = 1  # default: our team is the second value in each pair
    _ABBREV_RE = re.compile(r"^[A-Z]{2}$")
    for line in lines:
        tokens = line.strip().split()
        if len(tokens) >= 2 and _ABBREV_RE.match(tokens[0]) and _ABBREV_RE.match(tokens[1]):
            found_our_col = False
            for tok_idx, tok in enumerate(tokens[:2]):
                if tok == our_abbrev:
                    our_col = tok_idx
                    found_our_col = True
                    break
            if not found_our_col:
                import warnings
                warnings.warn(
                    f"team_stats: abbreviation '{our_abbrev}' not found in header "
                    f"row tokens {tokens[:2]!r}; defaulting to our_col=1",
                    stacklevel=2,
                )
            break

    # Track context: have we passed the short-handed section header?
    in_sh_section = False

    for line in lines:
        stripped = line.strip()

        # Track section context
        if "Short-handed play" in stripped or "Short-handed minutes" in stripped:
            in_sh_section = True

        # --- pp_time_seconds_total ---
        # "Power play minutes played 07:09 09:44"
        m = re.search(r"Power play minutes played\s+(\S+)\s+(\S+)", stripped)
        if m:
            vals = [m.group(1), m.group(2)]
            result["pp_time_seconds_total"] = _parse_time_to_seconds(vals[our_col])

        # --- pp_time_seconds_in_oz ---
        # "Out of which in offensive zone 05:17 05:36"
        # This line can be embedded within a longer text line
        m = re.search(r"Out of which in offensive zone\s+(\S+)\s+(\S+)", stripped)
        if m:
            vals = [m.group(1), m.group(2)]
            result["pp_time_seconds_in_oz"] = _parse_time_to_seconds(vals[our_col])

        # --- pp_shots ---
        # "Power play 17 / 12 / 1 15 / 6 / 0 ..."
        # The PP row in "Shots and goals scored" section has format:
        #   "Power play <n1> / <n2> / <n3> <n4> / <n5> / <n6> ..."
        # We want the first number of the second group (our_col=1 → n4)
        m = re.search(
            r"Power play\s+(\d+)\s*/\s*(\d+)\s*/\s*(\d+)\s+(\d+)\s*/\s*(\d+)\s*/\s*(\d+)",
            stripped,
        )
        if m:
            # Groups: PT_shots, PT_og, PT_goals, HC_shots, HC_og, HC_goals
            if our_col == 0:
                result["pp_shots"] = int(m.group(1))
            else:
                result["pp_shots"] = int(m.group(4))

        # --- pp_opp_breakouts_allowed ---
        # "Opp breakouts 2 6"  (in PP section; may be at end of a longer line)
        m = re.search(r"Opp breakouts\s+(\d+)\s+(\d+)", stripped)
        if m:
            vals = [m.group(1), m.group(2)]
            result["pp_opp_breakouts_allowed"] = _parse_int(vals[our_col])

        # --- pk_opp_breakouts ---
        # "Breakouts 6 2"  (in short-handed section; may be at end of a longer line)
        # Gate on in_sh_section to avoid false-matching a "PP Breakouts" row if
        # InStat ever reorders lines — both rows share the same "Breakouts N N" shape.
        if in_sh_section:
            m = re.search(r"Breakouts\s+(\d+)\s+(\d+)\s*$", stripped)
            if m:
                vals = [m.group(1), m.group(2)]
                result["pk_opp_breakouts"] = _parse_int(vals[our_col])

        # --- puck_possession_seconds_total ---
        # "Puck possessions 19:57 16:20 Puck possessions 91 90 ..."
        # Match the first time-pair only (MM:SS format)
        m = re.search(r"^Puck possessions\s+(\d+:\d{2})\s+(\d+:\d{2})", stripped)
        if m:
            vals = [m.group(1), m.group(2)]
            result["puck_possession_seconds_total"] = _parse_time_to_seconds(vals[our_col])

        # --- oz_possession_seconds and oz_possession_pct ---
        # "Offensive zone 09:57 50% 06:26 39%"
        # This pattern appears twice (Puck losses and OZ possession sections);
        # we want the one in the puck-possession section (has time values).
        # Pattern: "Offensive zone <time> <pct>% <time> <pct>%"
        m = re.match(
            r"^Offensive zone\s+(\d+:\d{2})\s+(\d+)%\s+(\d+:\d{2})\s+(\d+)%",
            stripped,
        )
        if m:
            if our_col == 0:
                result["oz_possession_seconds"] = _parse_time_to_seconds(m.group(1))
                result["oz_possession_pct"] = _parse_pct(m.group(2) + "%")
            else:
                result["oz_possession_seconds"] = _parse_time_to_seconds(m.group(3))
                result["oz_possession_pct"] = _parse_pct(m.group(4) + "%")

        # --- scoring_chance_shots and scoring_chance_shots_on_goal ---
        # "Shots from a scoring chance area 33 / 24 / 4 17 / 11 / 1"
        m = re.match(
            r"Shots from a scoring chance area\s+(\d+)\s*/\s*(\d+)\s*/\s*\d+\s+(\d+)\s*/\s*(\d+)\s*/\s*\d+",
            stripped,
        )
        if m:
            if our_col == 0:
                result["scoring_chance_shots"] = int(m.group(1))
                result["scoring_chance_shots_on_goal"] = int(m.group(2))
            else:
                result["scoring_chance_shots"] = int(m.group(3))
                result["scoring_chance_shots_on_goal"] = int(m.group(4))


def _team_abbrev(team_name: str) -> str:
    """Extract 2-letter abbreviation from a team name.

    "HARVARD CRIMSON" -> "HC"
    "PRINCETON TIGERS" -> "PT"
    """
    parts = [p for p in team_name.strip().split() if p]
    if len(parts) >= 2:
        return parts[0][0] + parts[1][0]
    return team_name[:2].upper()


def _parse_time_to_seconds(s: str) -> Optional[int]:
    """Parse InStat time strings like '05:23' or '1:23:45' to seconds."""
    if not s or s.strip() == "\u2014":
        return None
    m = re.match(r"^(?:(\d+):)?(\d+):(\d+)$", s.strip())
    if not m:
        return None
    h = int(m.group(1) or 0)
    mm, ss = int(m.group(2)), int(m.group(3))
    return h * 3600 + mm * 60 + ss


def _parse_pct(s: str) -> Optional[float]:
    """Parse a percentage string to a fraction in [0, 1].

    Accepts '39%' (-> 0.39), '0.39' (-> 0.39, already-normalized), or '—' (-> None).
    Values > 1.0 are interpreted as percentages and divided by 100;
    values in [0, 1] are treated as already-normalized fractions.

    Callers reading raw percentages from PDF text should pass the '%'
    suffix to disambiguate integer inputs like '1' (which would otherwise
    be misread as 0.01 rather than 1.0).
    """
    if not s or s.strip() == "\u2014":
        return None
    s = s.strip().rstrip("%")
    try:
        val = float(s)
    except ValueError:
        return None
    return val / 100.0 if val > 1.0 else val


def _parse_int(s: str) -> Optional[int]:
    if not s or s.strip() == "\u2014":
        return None
    try:
        return int(s.strip())
    except ValueError:
        return None
