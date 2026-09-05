import pytest
from app.tier2_stats import special_teams_v2
from app.models import TeamGameStatsInStat


def _row(pp_shots=None, pp_time_seconds_total=None, pp_time_seconds_in_oz=None,
         pk_opp_breakouts=None, pp_opp_breakouts_allowed=None):
    r = TeamGameStatsInStat(game_id=1)
    r.pp_shots = pp_shots
    r.pp_time_seconds_total = pp_time_seconds_total
    r.pp_time_seconds_in_oz = pp_time_seconds_in_oz
    r.pk_opp_breakouts = pk_opp_breakouts
    r.pp_opp_breakouts_allowed = pp_opp_breakouts_allowed
    return r


class TestSpecialTeamsV2:
    def test_empty(self):
        r = special_teams_v2([])
        assert r == {
            "pp_shots_per_min": None, "pp_oz_ratio": None,
            "pk_opp_breakout_rate": None, "pp_minutes": None,
            "pk_count": 0, "games": 0,
        }

    def test_single_game(self):
        rows = [_row(pp_shots=12, pp_time_seconds_total=600,
                     pp_time_seconds_in_oz=360, pk_opp_breakouts=2)]
        r = special_teams_v2(rows)
        assert r["pp_shots_per_min"] == pytest.approx(12 / 10.0)
        assert r["pp_oz_ratio"] == pytest.approx(0.6)
        assert r["pk_opp_breakout_rate"] == pytest.approx(2.0)  # 2 breakouts / 1 pk game
        assert r["pp_minutes"] == pytest.approx(10.0)
        assert r["pk_count"] == 1
        assert r["games"] == 1

    def test_multi_game(self):
        rows = [_row(pp_shots=10, pp_time_seconds_total=300, pp_time_seconds_in_oz=180,
                     pk_opp_breakouts=1),
                _row(pp_shots=15, pp_time_seconds_total=600, pp_time_seconds_in_oz=300,
                     pk_opp_breakouts=3)]
        r = special_teams_v2(rows)
        assert r["pp_shots_per_min"] == pytest.approx(25 / 15.0)
        assert r["pp_oz_ratio"] == pytest.approx(480 / 900)
        assert r["pk_opp_breakout_rate"] == pytest.approx(4 / 2)
        assert r["pp_minutes"] == pytest.approx(15.0)
        assert r["pk_count"] == 2
        assert r["games"] == 2

    def test_pp_time_zero_returns_none_rates(self):
        rows = [_row(pp_shots=None, pp_time_seconds_total=0, pp_time_seconds_in_oz=0)]
        r = special_teams_v2(rows)
        assert r["pp_shots_per_min"] is None
        assert r["pp_oz_ratio"] is None
        assert r["pp_minutes"] == 0.0
        assert r["games"] == 0  # no populated data, not counted

    def test_all_none_returns_none_rates(self):
        rows = [_row()]
        r = special_teams_v2(rows)
        assert r["pp_shots_per_min"] is None
        assert r["pp_oz_ratio"] is None
        assert r["pk_opp_breakout_rate"] is None
