import pytest
from app.tier2_stats import danger_zone_shot_share
from app.models import PlayerGameStatsInStat, TeamGameStatsInStat, PlayerGameStats


def _instat(shots=None):
    r = PlayerGameStatsInStat(game_id=1, player_id=1)
    r.shots = shots
    return r


def _team(scoring_chance_shots=None):
    r = TeamGameStatsInStat(game_id=1)
    r.scoring_chance_shots = scoring_chance_shots
    return r


def _pgs(toi_5v5=None):
    r = PlayerGameStats(game_id=1, player_id=1)
    r.toi_5v5 = toi_5v5
    return r


class TestDangerZoneShotShare:
    def test_empty(self):
        r = danger_zone_shot_share([], [], [])
        assert r == {
            "share_pct": None, "shots_per_60": None,
            "player_sca_shots": 0, "team_sca_shots": 0, "games": 0,
        }

    def test_basic_share(self):
        instat = [_instat(shots=4), _instat(shots=6)]
        team = [_team(scoring_chance_shots=20), _team(scoring_chance_shots=25)]
        pgs = [_pgs(toi_5v5=15.0), _pgs(toi_5v5=18.0)]
        r = danger_zone_shot_share(instat, team, pgs)
        assert r["player_sca_shots"] == 10
        assert r["team_sca_shots"] == 45
        assert r["share_pct"] == pytest.approx(10 / 45)
        assert r["shots_per_60"] == pytest.approx(10 * 60 / 33.0)
        assert r["games"] == 2

    def test_zero_team_sca_returns_none_share(self):
        instat = [_instat(shots=3)]
        team = [_team(scoring_chance_shots=0)]
        pgs = [_pgs(toi_5v5=10.0)]
        r = danger_zone_shot_share(instat, team, pgs)
        assert r["share_pct"] is None
        assert r["shots_per_60"] == pytest.approx(3 * 60 / 10.0)

    def test_zero_toi_returns_none_per_60(self):
        instat = [_instat(shots=3)]
        team = [_team(scoring_chance_shots=10)]
        pgs = []
        r = danger_zone_shot_share(instat, team, pgs)
        assert r["share_pct"] == pytest.approx(3 / 10)
        assert r["shots_per_60"] is None

    def test_none_shots_treated_as_zero(self):
        instat = [_instat(shots=None), _instat(shots=5)]
        team = [_team(scoring_chance_shots=10)]
        pgs = [_pgs(toi_5v5=10.0)]
        r = danger_zone_shot_share(instat, team, pgs)
        assert r["player_sca_shots"] == 5
        assert r["team_sca_shots"] == 10
