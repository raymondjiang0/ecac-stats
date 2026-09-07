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

    def test_zero_player_sca_with_toi_returns_none_per_60(self):
        """When player has InStat rows but zero shots and TOI > 0, shots_per_60 must be None.

        Returning 0.0 would be misleading — it signals 'no data available', not 'zero rate'.
        """
        instat = [_instat(shots=None)]  # shots=None -> val=0
        team = [_team(scoring_chance_shots=10)]
        pgs = [_pgs(toi_5v5=15.0)]
        r = danger_zone_shot_share(instat, team, pgs)
        assert r["player_sca_shots"] == 0
        assert r["shots_per_60"] is None  # must be None, not 0.0
        assert r["share_pct"] == 0.0  # 0/10 is a valid (zero) share


class TestDangerZoneWithShotsRows:
    def _shots_row(self, game_id=1, slot=0, center=0):
        from app.models import PlayerGameShotsInStat
        r = PlayerGameShotsInStat(player_id=1, game_id=game_id)
        r.slot_shots_total = slot
        r.center_shots_total = center
        return r

    def test_uses_slot_plus_center_when_shots_rows_provided(self):
        instat = [_instat(shots=99)]  # r.shots proxy would give 99
        team = [_team(scoring_chance_shots=20)]
        pgs = [_pgs(toi_5v5=15.0)]
        shots = [self._shots_row(slot=3, center=2)]  # true SCA = 5
        r = danger_zone_shot_share(instat, team, pgs, shots_rows=shots)
        # Numerator now 3+2=5, not 99
        assert r["player_sca_shots"] == 5
        assert r["share_pct"] == pytest.approx(5 / 20)
        assert r["shots_per_60"] == pytest.approx(5 * 60 / 15.0)

    def test_falls_back_to_shots_proxy_when_shots_rows_empty(self):
        instat = [_instat(shots=4)]
        team = [_team(scoring_chance_shots=10)]
        pgs = [_pgs(toi_5v5=10.0)]
        r = danger_zone_shot_share(instat, team, pgs, shots_rows=[])
        # Falls back to Phase 3 proxy: r.shots
        assert r["player_sca_shots"] == 4

    def test_falls_back_when_shots_rows_none(self):
        instat = [_instat(shots=4)]
        team = [_team(scoring_chance_shots=10)]
        pgs = [_pgs(toi_5v5=10.0)]
        r = danger_zone_shot_share(instat, team, pgs)  # no shots_rows
        assert r["player_sca_shots"] == 4

    def test_multi_game_shots_rows_aggregate(self):
        instat = [_instat(shots=99), _instat(shots=99)]
        team = [_team(scoring_chance_shots=30)]
        pgs = [_pgs(toi_5v5=20.0)]
        shots = [self._shots_row(game_id=1, slot=2, center=1),
                 self._shots_row(game_id=2, slot=3, center=2)]
        r = danger_zone_shot_share(instat, team, pgs, shots_rows=shots)
        assert r["player_sca_shots"] == 8  # 2+1+3+2
