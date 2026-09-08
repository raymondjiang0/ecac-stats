"""PDF section navigation for InStat match reports.

InStat's PDF layout is 19 pages with a symmetric per-team structure. Section
headers follow the pattern:

    <SECTION_NAME>: <TEAM NAME> <page number>

The match-wide TEAMS STATS section is an exception — it has no team suffix
because it's shared. We match sections by scanning the first ~5 lines of
each page's text; if the section is team-scoped, we also require the team
name to be present on the same line.
"""
from typing import Optional
import pdfplumber
from ..config import OUR_TEAM_NAME


# Section names as they appear in PDF headers
TEAMS_STATS_SECTION = "TEAMS STATS 2"           # match-wide
PLAYERS_STATS_SECTION = "PLAYERS' STATS"        # team-scoped
GAME_TIME_SECTION = "GAME TIME DISTRIBUTION"    # team-scoped
CHALLENGES_SECTION = "CHALLENGES"               # team-scoped
HITS_DISTRIBUTION_SECTION = "HITS DISTRIBUTION"     # team-scoped
PASSES_DISTRIBUTION_SECTION = "PASSES DISTRIBUTION" # team-scoped
SHOTS_SECTION = "SHOTS"                              # team-scoped


# Match-wide sections don't carry a team suffix
_MATCH_WIDE_SECTIONS = {TEAMS_STATS_SECTION}


def find_section_page(
    pdf: pdfplumber.PDF, section: str, team: str
) -> Optional[int]:
    """Locate the 0-indexed page containing `section` for `team`.

    For match-wide sections (TEAMS STATS 2), the team argument is ignored.
    Returns None if the section isn't found or the team suffix doesn't match.
    """
    is_match_wide = section in _MATCH_WIDE_SECTIONS
    # First pass: check line 1 (the main header line for actual content pages)
    for i, page in enumerate(pdf.pages):
        text = page.extract_text() or ""
        lines = text.splitlines()[:5]
        if len(lines) > 1:
            line = lines[1]
            if section not in line:
                continue
            if is_match_wide:
                return i
            # Team-scoped: require the team name on the same header line
            if team in line:
                return i

    # Second pass: rescan every page (not just those pass 1 skipped) on
    # the remaining lines. Kept simple over incremental tracking — 19 pages
    # is negligible.
    for i, page in enumerate(pdf.pages):
        text = page.extract_text() or ""
        lines = text.splitlines()[:5]
        for line_idx, line in enumerate(lines):
            if line_idx == 1:  # Skip line 1 (already checked)
                continue
            if section not in line:
                continue
            # For match-wide sections, skip the cover page (page 0)
            if is_match_wide and i == 0:
                continue
            if is_match_wide:
                return i
            # Team-scoped: require the team name on the same header line
            if team in line:
                return i
    return None


def find_our_team_section_page(
    pdf: pdfplumber.PDF, section: str
) -> Optional[int]:
    """Convenience wrapper: locate a section for OUR_TEAM_NAME."""
    return find_section_page(pdf, section, OUR_TEAM_NAME)
