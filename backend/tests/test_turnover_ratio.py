import pytest
from app.tier2_stats import turnover_location_ratio
from app.models import PlayerGameStatsInStat


def _row(puck_losses=None, puck_losses_dz=None, puck_recoveries=None, puck_recoveries_oz=None):
    r = PlayerGameStatsInStat(game_id=1, player_id=1)
    r.puck_losses = puck_losses
    r.puck_losses_dz = puck_losses_dz
    r.puck_recoveries = puck_recoveries
    r.puck_recoveries_oz = puck_recoveries_oz
    return r


class TestTurnoverLocationRatio:
    def test_empty(self):
        assert turnover_location_ratio([]) == {
            "dz_loss_share": None, "oz_recovery_share": None,
            "total_losses": 0, "total_recoveries": 0, "games": 0,
        }

    def test_single_game(self):
        rows = [_row(6, 2, 8, 3)]
        r = turnover_location_ratio(rows)
        assert r["dz_loss_share"] == pytest.approx(2 / 6)
        assert r["oz_recovery_share"] == pytest.approx(3 / 8)
        assert r["total_losses"] == 6
        assert r["total_recoveries"] == 8
        assert r["games"] == 1

    def test_multi_game_aggregates(self):
        rows = [_row(6, 2, 8, 3), _row(4, 1, 5, 2)]
        r = turnover_location_ratio(rows)
        assert r["dz_loss_share"] == pytest.approx(3 / 10)
        assert r["oz_recovery_share"] == pytest.approx(5 / 13)

    def test_zero_losses_returns_none_share(self):
        rows = [_row(0, 0, 5, 2)]
        r = turnover_location_ratio(rows)
        assert r["dz_loss_share"] is None
        assert r["oz_recovery_share"] == pytest.approx(2 / 5)

    def test_none_fields_treated_as_zero(self):
        rows = [_row(None, None, None, None)]
        r = turnover_location_ratio(rows)
        assert r["dz_loss_share"] is None
        assert r["oz_recovery_share"] is None
        assert r["games"] == 0
