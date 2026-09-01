import os
import pytest
import pdfplumber
from app.ingest.parsers.players_main import parse_players_main

FIXTURE = os.path.join(os.path.dirname(__file__), "fixtures", "instat_sample.pdf")


@pytest.fixture
def pdf():
    with pdfplumber.open(FIXTURE) as p:
        yield p


class TestParsePlayersMain:
    def test_returns_list_of_dicts(self, pdf):
        rows = parse_players_main(pdf, our_team="HARVARD CRIMSON")
        assert isinstance(rows, list)
        assert all(isinstance(r, dict) for r in rows)

    def test_reasonable_row_count(self, pdf):
        # Harvard fixture has ~16 skaters + 1 goalie; parser should return
        # a substantial number, not 0 or a handful
        rows = parse_players_main(pdf, our_team="HARVARD CRIMSON")
        assert 10 <= len(rows) <= 25, f"got {len(rows)} rows"

    def test_each_row_has_jersey_and_name(self, pdf):
        rows = parse_players_main(pdf, our_team="HARVARD CRIMSON")
        for r in rows:
            assert "jersey_number" in r and r["jersey_number"]
            assert "player_name" in r and r["player_name"]

    def test_jersey_numbers_are_strings(self, pdf):
        # Match Player.number column type (String)
        rows = parse_players_main(pdf, our_team="HARVARD CRIMSON")
        for r in rows:
            assert isinstance(r["jersey_number"], str)

    def test_numeric_fields_are_int_or_none(self, pdf):
        rows = parse_players_main(pdf, our_team="HARVARD CRIMSON")
        numeric_keys = {
            "shots", "shots_on_goal", "blocked_shots",
            "pp_shots", "pp_shots_on_goal",
            "corsi_plus", "corsi_minus",
            "hits_delivered", "hits_received",
            "puck_losses", "puck_losses_dz",
            "puck_recoveries", "puck_recoveries_oz",
            "entries_pass", "entries_stick", "entries_dump",
        }
        for r in rows:
            for k in numeric_keys & r.keys():
                assert r[k] is None or isinstance(r[k], int), (
                    f"player {r['player_name']!r} field {k}={r[k]!r} not int/None"
                )

    def test_returns_empty_for_unknown_team(self, pdf):
        rows = parse_players_main(pdf, our_team="NONEXISTENT TEAM")
        assert rows == []
