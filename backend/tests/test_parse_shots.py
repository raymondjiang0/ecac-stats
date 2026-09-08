import os
import pytest
import pdfplumber
from app.ingest.parsers.shots import parse_shots

FIXTURE = os.path.join(os.path.dirname(__file__), "fixtures", "instat_sample.pdf")


@pytest.fixture
def pdf():
    with pdfplumber.open(FIXTURE) as p:
        yield p


class TestParseShots:
    def test_returns_list_of_dicts(self, pdf):
        rows = parse_shots(pdf, our_team="HARVARD CRIMSON")
        assert isinstance(rows, list)
        assert all(isinstance(r, dict) for r in rows)

    def test_reasonable_row_count(self, pdf):
        # Harvard fixture has ~16 skaters
        rows = parse_shots(pdf, our_team="HARVARD CRIMSON")
        assert 10 <= len(rows) <= 25, f"got {len(rows)} rows"

    def test_each_row_has_jersey_and_name(self, pdf):
        rows = parse_shots(pdf, our_team="HARVARD CRIMSON")
        for r in rows:
            assert "jersey_number" in r and isinstance(r["jersey_number"], str)
            assert "player_name" in r and isinstance(r["player_name"], str)

    def test_expected_fields_present_or_none(self, pdf):
        rows = parse_shots(pdf, our_team="HARVARD CRIMSON")
        expected_keys = {
            "goals", "shots_total", "shots_on_goal", "shots_blocked_defensively",
            "pp_shots_total", "pp_shots_on_goal",
            "sh_shots_total", "sh_shots_on_goal",
            "positional_shots_total", "positional_shots_on_goal",
            "counter_shots_total", "counter_shots_on_goal",
            "slot_shots_total", "slot_shots_on_goal",
            "center_shots_total", "center_shots_on_goal",
            "right_flank_shots_total", "right_flank_shots_on_goal",
            "left_flank_shots_total", "left_flank_shots_on_goal",
            "blue_line_right_shots_total", "blue_line_right_shots_on_goal",
            "blue_line_center_shots_total", "blue_line_center_shots_on_goal",
            "blue_line_left_shots_total", "blue_line_left_shots_on_goal",
            "slapshot_total", "slapshot_on_goal",
            "wristshot_total", "wristshot_on_goal",
        }
        for r in rows:
            for k in expected_keys:
                assert k in r, f"missing key {k} in row {r['player_name']}"
                assert r[k] is None or isinstance(r[k], int), (
                    f"{r['player_name']} {k}={r[k]!r} not int/None"
                )

    def test_shots_on_goal_never_exceeds_shots_total(self, pdf):
        rows = parse_shots(pdf, our_team="HARVARD CRIMSON")
        pair_prefixes = [
            "shots", "pp_shots", "sh_shots",
            "positional_shots", "counter_shots",
            "slot_shots", "center_shots",
            "right_flank_shots", "left_flank_shots",
            "blue_line_right_shots", "blue_line_center_shots", "blue_line_left_shots",
            "slapshot", "wristshot",
        ]
        for r in rows:
            for prefix in pair_prefixes:
                # shots_total maps to shots + _total, but shots itself is special
                total_key = f"{prefix}_total" if prefix != "shots" else "shots_total"
                on_goal_key = f"{prefix}_on_goal"
                t, og = r.get(total_key), r.get(on_goal_key)
                if t is not None and og is not None:
                    assert og <= t, f"{r['player_name']} {on_goal_key}={og} > {total_key}={t}"

    def test_returns_empty_for_unknown_team(self, pdf):
        assert parse_shots(pdf, our_team="NONEXISTENT TEAM") == []

    def test_at_least_one_populated_field(self, pdf):
        # Guard against silent all-None parse
        rows = parse_shots(pdf, our_team="HARVARD CRIMSON")
        populated_counts = [
            sum(1 for k, v in r.items() if v is not None and k not in ("jersey_number", "player_name"))
            for r in rows
        ]
        assert max(populated_counts) >= 3, "no row has >=3 populated numeric fields"
