import pytest
from app.tier3_stats import defensive_disruption_index
from app.models import PlayerGameStats, PlayerGameStatsInStat, PlayerGameShotsInStat


def _pgs(game_id=1, toi_5v5=15.0):
    r = PlayerGameStats(player_id=1, game_id=game_id)
    r.toi_5v5 = toi_5v5
    return r


def _instat(game_id=1, puck_recoveries=None, pb_won_dz=None):
    r = PlayerGameStatsInStat(player_id=1, game_id=game_id)
    r.puck_recoveries = puck_recoveries
    r.pb_won_dz = pb_won_dz
    return r


def _shots(game_id=1, shots_blocked_defensively=None):
    r = PlayerGameShotsInStat(player_id=1, game_id=game_id)
    r.shots_blocked_defensively = shots_blocked_defensively
    return r


class TestDefensiveDisruptionIndex:
    def test_empty_returns_none(self):
        r = defensive_disruption_index([], [], [])
        assert r["ddi_per_60"] is None
        assert r["components"] == {"puck_recoveries": 0,
                                    "shots_blocked_defensively": 0,
                                    "dz_pb_wins": 0}
        assert r["total_toi_minutes"] == 0.0
        assert r["games"] == 0

    def test_single_game_all_components(self):
        pgs = [_pgs(toi_5v5=15.0)]
        instat = [_instat(puck_recoveries=8, pb_won_dz=3)]
        shots = [_shots(shots_blocked_defensively=4)]
        r = defensive_disruption_index(pgs, instat, shots)
        # (8 + 4 + 3) × 60 / 15 = 60
        assert r["ddi_per_60"] == pytest.approx(60.0)
        assert r["components"] == {"puck_recoveries": 8,
                                    "shots_blocked_defensively": 4,
                                    "dz_pb_wins": 3}
        assert r["total_toi_minutes"] == pytest.approx(15.0)
        assert r["games"] == 1

    def test_multi_game_aggregate(self):
        pgs = [_pgs(game_id=1, toi_5v5=15.0), _pgs(game_id=2, toi_5v5=20.0)]
        instat = [_instat(game_id=1, puck_recoveries=6, pb_won_dz=2),
                  _instat(game_id=2, puck_recoveries=4, pb_won_dz=1)]
        shots = [_shots(game_id=1, shots_blocked_defensively=3),
                 _shots(game_id=2, shots_blocked_defensively=1)]
        r = defensive_disruption_index(pgs, instat, shots)
        # (10 + 4 + 3) × 60 / 35 = 29.14...
        assert r["ddi_per_60"] == pytest.approx(17 * 60 / 35)
        assert r["games"] == 2

    def test_missing_component_returns_none(self):
        # Recoveries and DZ PB wins present, but zero shots blocking data
        pgs = [_pgs(toi_5v5=15.0)]
        instat = [_instat(puck_recoveries=8, pb_won_dz=3)]
        shots = [_shots(shots_blocked_defensively=None)]  # no data
        r = defensive_disruption_index(pgs, instat, shots)
        assert r["ddi_per_60"] is None
        # Components still show the counts we did aggregate
        assert r["components"]["puck_recoveries"] == 8

    def test_zero_toi_returns_none(self):
        pgs = [_pgs(toi_5v5=0.0)]
        instat = [_instat(puck_recoveries=8, pb_won_dz=3)]
        shots = [_shots(shots_blocked_defensively=4)]
        r = defensive_disruption_index(pgs, instat, shots)
        assert r["ddi_per_60"] is None

    def test_none_values_treated_as_zero_when_at_least_one_row_has_data(self):
        # One game with data, one game with None fields for a component
        pgs = [_pgs(game_id=1, toi_5v5=15.0), _pgs(game_id=2, toi_5v5=15.0)]
        instat = [_instat(game_id=1, puck_recoveries=5, pb_won_dz=2),
                  _instat(game_id=2, puck_recoveries=None, pb_won_dz=None)]
        shots = [_shots(game_id=1, shots_blocked_defensively=3),
                 _shots(game_id=2, shots_blocked_defensively=2)]
        r = defensive_disruption_index(pgs, instat, shots)
        # recoveries: 5 + 0 = 5 (has_data=True from game 1)
        # blocks: 3 + 2 = 5 (has_data=True)
        # dz_pb: 2 + 0 = 2 (has_data=True)
        assert r["components"]["puck_recoveries"] == 5
        assert r["components"]["shots_blocked_defensively"] == 5
        assert r["components"]["dz_pb_wins"] == 2
        # 12 × 60 / 30 = 24
        assert r["ddi_per_60"] == pytest.approx(24.0)

    def test_zero_valued_component_still_counts_as_game(self):
        """Zero values are valid data — a game with puck_recoveries=0 and
        pb_won_dz=0 (both non-None) should count as 1 game, not 0."""
        pgs = [_pgs(toi_5v5=15.0)]
        instat = [_instat(puck_recoveries=0, pb_won_dz=0)]
        shots = [_shots(shots_blocked_defensively=0)]
        r = defensive_disruption_index(pgs, instat, shots)
        assert r["games"] == 1
        # All three components are 0, all have_data flags True → ddi_per_60 = 0.0
        assert r["ddi_per_60"] == pytest.approx(0.0)
