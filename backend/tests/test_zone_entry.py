import pytest
from app.tier2_stats import zone_entry_composition
from app.models import PlayerGameStatsInStat


def _row(entries_pass=None, entries_stick=None, entries_dump=None):
    r = PlayerGameStatsInStat(game_id=1, player_id=1)
    r.entries_pass = entries_pass
    r.entries_stick = entries_stick
    r.entries_dump = entries_dump
    return r


class TestZoneEntryComposition:
    def test_empty_returns_none_pcts(self):
        assert zone_entry_composition([]) == {
            "pass_pct": None, "stick_pct": None, "dump_pct": None,
            "total_entries": 0, "games": 0,
        }

    def test_single_game(self):
        rows = [_row(3, 4, 2)]
        r = zone_entry_composition(rows)
        assert r["pass_pct"] == pytest.approx(3 / 9)
        assert r["stick_pct"] == pytest.approx(4 / 9)
        assert r["dump_pct"] == pytest.approx(2 / 9)
        assert r["total_entries"] == 9
        assert r["games"] == 1

    def test_multi_game_aggregates(self):
        rows = [_row(3, 4, 2), _row(1, 2, 1)]
        r = zone_entry_composition(rows)
        assert r["pass_pct"] == pytest.approx(4 / 13)
        assert r["stick_pct"] == pytest.approx(6 / 13)
        assert r["dump_pct"] == pytest.approx(3 / 13)
        assert r["total_entries"] == 13
        assert r["games"] == 2

    def test_all_zero_returns_none(self):
        rows = [_row(0, 0, 0), _row(None, None, None)]
        r = zone_entry_composition(rows)
        assert r["pass_pct"] is None
        assert r["stick_pct"] is None
        assert r["dump_pct"] is None
        assert r["total_entries"] == 0
        assert r["games"] == 0

    def test_none_fields_treated_as_zero(self):
        rows = [_row(None, 5, None)]
        r = zone_entry_composition(rows)
        assert r["pass_pct"] == pytest.approx(0.0)
        assert r["stick_pct"] == pytest.approx(1.0)
        assert r["dump_pct"] == pytest.approx(0.0)
        assert r["total_entries"] == 5
        assert r["games"] == 1
