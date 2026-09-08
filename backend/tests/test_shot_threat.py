import pytest
from app.tier3_stats import shot_threat_by_scenario
from app.models import PlayerGameShotsInStat, PlayerGameStats


def _shots(game_id=1, **kwargs):
    r = PlayerGameShotsInStat(player_id=1, game_id=game_id)
    for k, v in kwargs.items():
        setattr(r, k, v)
    return r


def _pgs(game_id=1, toi_5v5=15.0, toi_pp=2.0, toi_sh=1.0):
    r = PlayerGameStats(player_id=1, game_id=game_id)
    r.toi_5v5 = toi_5v5
    r.toi_pp = toi_pp
    r.toi_sh = toi_sh
    return r


class TestShotThreatByScenario:
    def test_empty_returns_zero_shape(self):
        r = shot_threat_by_scenario([], [])
        assert r["games"] == 0
        assert r["totals"]["shots"] == 0
        assert r["by_strength"]["5v5"]["shots"] == 0
        assert r["by_strength"]["5v5"]["shots_per_60"] is None

    def test_single_game_totals(self):
        shots = [_shots(goals=1, shots_total=5, shots_on_goal=3,
                        pp_shots_total=1, pp_shots_on_goal=1,
                        slot_shots_total=2, slot_shots_on_goal=2,
                        wristshot_total=4, wristshot_on_goal=2)]
        pgs = [_pgs()]
        r = shot_threat_by_scenario(shots, pgs)
        assert r["totals"]["goals"] == 1
        assert r["totals"]["shots"] == 5
        assert r["totals"]["shots_on_goal"] == 3
        assert r["totals"]["toi_5v5_minutes"] == pytest.approx(15.0)
        assert r["games"] == 1

    def test_by_strength_split(self):
        shots = [_shots(shots_total=5, shots_on_goal=3,
                        pp_shots_total=1, pp_shots_on_goal=1,
                        sh_shots_total=0, sh_shots_on_goal=0)]
        pgs = [_pgs(toi_5v5=10.0, toi_pp=2.0, toi_sh=1.0)]
        r = shot_threat_by_scenario(shots, pgs)
        # 5v5 shots = total - pp - sh = 5 - 1 - 0 = 4
        assert r["by_strength"]["5v5"]["shots"] == 4
        assert r["by_strength"]["5v5"]["on_goal"] == 2  # 3 - 1 - 0
        # shots_per_60 at 5v5 = 4 * 60 / 10.0 = 24.0
        assert r["by_strength"]["5v5"]["shots_per_60"] == pytest.approx(24.0)
        assert r["by_strength"]["pp"]["shots_per_60"] == pytest.approx(30.0)  # 1*60/2
        assert r["by_strength"]["sh"]["shots"] == 0
        assert r["by_strength"]["sh"]["shots_per_60"] is None  # zero shots

    def test_by_location(self):
        shots = [_shots(slot_shots_total=3, slot_shots_on_goal=2,
                        center_shots_total=1, center_shots_on_goal=1,
                        right_flank_shots_total=2, right_flank_shots_on_goal=1)]
        pgs = [_pgs()]
        r = shot_threat_by_scenario(shots, pgs)
        assert r["by_location"]["slot"]["shots"] == 3
        assert r["by_location"]["slot"]["on_goal"] == 2
        assert r["by_location"]["slot"]["on_goal_pct"] == pytest.approx(2/3)
        assert r["by_location"]["center"]["shots"] == 1
        assert r["by_location"]["right_flank"]["on_goal_pct"] == pytest.approx(0.5)
        # Unpopulated location returns 0 shots + None pct
        assert r["by_location"]["left_flank"]["shots"] == 0
        assert r["by_location"]["left_flank"]["on_goal_pct"] is None

    def test_by_context(self):
        shots = [_shots(positional_shots_total=3, positional_shots_on_goal=2,
                        counter_shots_total=1, counter_shots_on_goal=1)]
        r = shot_threat_by_scenario(shots, [_pgs()])
        assert r["by_context"]["positional"]["shots"] == 3
        assert r["by_context"]["counter"]["shots"] == 1

    def test_by_type(self):
        shots = [_shots(slapshot_total=1, slapshot_on_goal=1,
                        wristshot_total=4, wristshot_on_goal=2)]
        r = shot_threat_by_scenario(shots, [_pgs()])
        assert r["by_type"]["slapshot"]["shots"] == 1
        assert r["by_type"]["wristshot"]["on_goal_pct"] == pytest.approx(0.5)

    def test_multi_game_aggregates(self):
        shots = [_shots(game_id=1, shots_total=3, shots_on_goal=2, slot_shots_total=2, slot_shots_on_goal=2),
                 _shots(game_id=2, shots_total=4, shots_on_goal=3, slot_shots_total=1, slot_shots_on_goal=1)]
        pgs = [_pgs(game_id=1, toi_5v5=15.0), _pgs(game_id=2, toi_5v5=20.0)]
        r = shot_threat_by_scenario(shots, pgs)
        assert r["totals"]["shots"] == 7
        assert r["totals"]["toi_5v5_minutes"] == pytest.approx(35.0)
        assert r["by_location"]["slot"]["shots"] == 3
        assert r["games"] == 2

    def test_no_toi_returns_none_rates(self):
        shots = [_shots(shots_total=5, shots_on_goal=3)]
        pgs = [_pgs(toi_5v5=0.0, toi_pp=0.0, toi_sh=0.0)]
        r = shot_threat_by_scenario(shots, pgs)
        assert r["by_strength"]["5v5"]["shots_per_60"] is None
        assert r["by_strength"]["pp"]["shots_per_60"] is None
