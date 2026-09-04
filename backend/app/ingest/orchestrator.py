"""Run every InStat template against a single PDF.

Returns {"templates": {name: parsed_data}, "warnings": [str, ...]}.
Warnings are non-fatal notes for the review UI (e.g. team not found,
sections missing).
"""
import pdfplumber
from .templates import TEMPLATES
from .pdf_nav import (
    find_section_page,
    PLAYERS_STATS_SECTION,
)


def parse_all(pdf_path: str, our_team: str) -> dict:
    """Run all six template parsers on one PDF.

    pdf_path: filesystem path to an InStat match-report PDF.
    our_team: team name to extract data for (e.g. "HARVARD CRIMSON").
    Returns {"templates": {name: parsed_data}, "warnings": [...]}.
    """
    templates_out = {}
    warnings = []
    with pdfplumber.open(pdf_path) as pdf:
        # Sanity check: our team's players' stats section must exist
        players_page = find_section_page(pdf, PLAYERS_STATS_SECTION, our_team)
        if players_page is None:
            warnings.append(
                f"Team {our_team!r} not found in PDF; parsers returned empty data."
            )
        for name, parser in TEMPLATES.items():
            templates_out[name] = parser(pdf, our_team)
    return {"templates": templates_out, "warnings": warnings}
