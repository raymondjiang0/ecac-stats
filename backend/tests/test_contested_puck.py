import pytest
from app.tier2_stats import contested_puck_win_pct
from app.models import PlayerGameStatsInStat


def _row(pb_won_dz=None, pb_total_dz=None, pb_won_oz=None, pb_total_oz=None,
         pb_won_nz=None, pb_total_nz=None):
    r = PlayerGameStatsInStat(game_id=1, player_id=1)
    r.pb_won_dz = pb_won_dz
    r.pb_total_dz = pb_total_dz
    r.pb_won_oz = pb_won_oz
    r.pb_total_oz = pb_total_oz
    r.pb_won_nz = pb_won_nz
    r.pb_total_nz = pb_total_nz
    return r


class TestContestedPuckWinPct:
    def test_empty_returns_all_none(self):
        result = contested_puck_win_pct([])
        assert result == {
            "overall_pct": None, "dz_pct": None,
            "oz_pct": None, "nz_pct": None, "games": 0,
        }

    def test_single_game_all_zones(self):
        rows = [_row(3, 5, 4, 6, 2, 4)]
        r = contested_puck_win_pct(rows)
        assert r["dz_pct"] == pytest.approx(0.6)
        assert r["oz_pct"] == pytest.approx(4/6)
        assert r["nz_pct"] == pytest.approx(0.5)
        assert r["overall_pct"] == pytest.approx(9 / 15)
        assert r["games"] == 1

    def test_multi_game_aggregates_won_and_total(self):
        rows = [_row(3, 5, 2, 4, 1, 2), _row(4, 8, 3, 6, 2, 3)]
        r = contested_puck_win_pct(rows)
        assert r["dz_pct"] == pytest.approx(7 / 13)
        assert r["oz_pct"] == pytest.approx(5 / 10)
        assert r["nz_pct"] == pytest.approx(3 / 5)
        assert r["overall_pct"] == pytest.approx(15 / 28)
        assert r["games"] == 2

    def test_zone_with_zero_total_returns_none(self):
        rows = [_row(pb_won_dz=1, pb_total_dz=2)]  # OZ and NZ absent
        r = contested_puck_win_pct(rows)
        assert r["dz_pct"] == pytest.approx(0.5)
        assert r["oz_pct"] is None
        assert r["nz_pct"] is None
        # Overall computed from what's present
        assert r["overall_pct"] == pytest.approx(0.5)

    def test_none_fields_treated_as_zero(self):
        rows = [_row(None, None, 2, 4, None, None)]
        r = contested_puck_win_pct(rows)
        assert r["dz_pct"] is None
        assert r["oz_pct"] == pytest.approx(0.5)
        assert r["nz_pct"] is None

    def test_games_counts_rows_with_any_pb_total(self):
        rows = [_row(1, 2, None, None, None, None),
                _row(None, None, 3, 5, None, None),
                _row(None, None, None, None, None, None)]  # empty row not counted
        r = contested_puck_win_pct(rows)
        assert r["games"] == 2
