import os
import pytest
import pdfplumber
from app.ingest.parsers.players_main import parse_players_main, _parse_main_stats_line

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

    def test_apostrophe_name_not_silently_skipped(self):
        # Regression: names like O'Leary were dropped because the old guard
        # required ^[A-Z][a-z], failing on the apostrophe after the capital.
        # Construct a synthetic main-stats line with O'Leary as the name token.
        # Format: jersey name instat_idx goals assists points +/- TOI:MM shifts PPtime SHtime penalty shots/sog pct pp_shots corsi+ corsi- corsi_total hits_del hits_recv
        line = "17 O'Leary 123 0 1 1 0 12:34 15 2:00 0:00 2:00 3/2 66.7% 1/1 5 -3 2 2 1"
        row = _parse_main_stats_line(line)
        assert row is not None, "O'Leary should not be silently skipped"
        assert row["player_name"] == "O'Leary"
        assert row["jersey_number"] == "17"
