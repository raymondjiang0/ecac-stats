import os
import pytest
import pdfplumber
from app.ingest.pdf_nav import (
    find_section_page, find_our_team_section_page,
    TEAMS_STATS_SECTION, PLAYERS_STATS_SECTION,
    GAME_TIME_SECTION, CHALLENGES_SECTION,
    HITS_DISTRIBUTION_SECTION, PASSES_DISTRIBUTION_SECTION,
)

FIXTURE = os.path.join(os.path.dirname(__file__), "fixtures", "instat_sample.pdf")


@pytest.fixture
def pdf():
    with pdfplumber.open(FIXTURE) as p:
        yield p


class TestFindSectionPage:
    def test_teams_stats_on_page_2(self, pdf):
        # Teams stats section is match-wide (no team suffix); team parameter ignored
        assert find_section_page(pdf, TEAMS_STATS_SECTION, "HARVARD CRIMSON") == 1

    def test_harvard_players_on_page_11(self, pdf):
        assert find_section_page(pdf, PLAYERS_STATS_SECTION, "HARVARD CRIMSON") == 10

    def test_princeton_players_on_page_3(self, pdf):
        assert find_section_page(pdf, PLAYERS_STATS_SECTION, "PRINCETON TIGERS") == 2

    def test_harvard_hits_matrix_on_page_17(self, pdf):
        assert find_section_page(pdf, HITS_DISTRIBUTION_SECTION, "HARVARD CRIMSON") == 16

    def test_harvard_passes_matrix_on_page_18(self, pdf):
        assert find_section_page(pdf, PASSES_DISTRIBUTION_SECTION, "HARVARD CRIMSON") == 17

    def test_harvard_challenges_on_page_15(self, pdf):
        assert find_section_page(pdf, CHALLENGES_SECTION, "HARVARD CRIMSON") == 14

    def test_harvard_time_distribution_on_page_13(self, pdf):
        assert find_section_page(pdf, GAME_TIME_SECTION, "HARVARD CRIMSON") == 12

    def test_returns_none_when_team_not_found(self, pdf):
        assert find_section_page(pdf, PLAYERS_STATS_SECTION, "NONEXISTENT TEAM") is None


class TestFindOurTeamSectionPage:
    def test_defaults_to_our_team_name(self, pdf):
        # OUR_TEAM_NAME = "HARVARD CRIMSON" per app.config
        assert find_our_team_section_page(pdf, PLAYERS_STATS_SECTION) == 10
