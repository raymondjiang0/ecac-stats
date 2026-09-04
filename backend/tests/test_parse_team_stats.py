import os
import pytest
import pdfplumber
from app.ingest.parsers.team_stats import parse_team_stats

FIXTURE = os.path.join(os.path.dirname(__file__), "fixtures", "instat_sample.pdf")


@pytest.fixture
def pdf():
    with pdfplumber.open(FIXTURE) as p:
        yield p


class TestParseTeamStats:
    def test_returns_dict_with_expected_keys(self, pdf):
        result = parse_team_stats(pdf, our_team="HARVARD CRIMSON")
        expected_keys = {
            "pp_shots", "pp_time_seconds_in_oz", "pp_time_seconds_total",
            "pk_opp_breakouts", "pp_opp_breakouts_allowed",
            "puck_possession_seconds_total",
            "oz_possession_seconds", "oz_possession_pct",
            "scoring_chance_shots", "scoring_chance_shots_on_goal",
        }
        assert set(result.keys()) >= expected_keys

    def test_values_are_numeric_or_none(self, pdf):
        result = parse_team_stats(pdf, our_team="HARVARD CRIMSON")
        for key, val in result.items():
            assert val is None or isinstance(val, (int, float)), (
                f"{key}={val!r} is not numeric or None"
            )

    def test_percentage_field_is_normalized(self, pdf):
        # oz_possession_pct should be 0.0-1.0, not 0-100 (matches model type Float)
        result = parse_team_stats(pdf, our_team="HARVARD CRIMSON")
        pct = result.get("oz_possession_pct")
        if pct is not None:
            assert 0.0 <= pct <= 1.0, f"oz_possession_pct={pct} not in [0,1]"

    def test_returns_at_least_one_populated_field(self, pdf):
        # Guard against a parser that silently returns all-None
        result = parse_team_stats(pdf, our_team="HARVARD CRIMSON")
        populated = [k for k, v in result.items() if v is not None]
        assert len(populated) >= 3, (
            f"Only {len(populated)} fields populated: {populated}"
        )
