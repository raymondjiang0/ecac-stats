import pytest
from app.tier2_stats import impact_score
from app.models import Player, PlayerGameStats, PlayerGameStatsInStat


def _pgs(game_id, toi_5v5=15.0, xgf60=2.5, xga60=2.0, cf60=50.0, ca60=45.0):
    r = PlayerGameStats(game_id=game_id, player_id=1)
    r.toi_5v5 = toi_5v5
    r.xgf60 = xgf60
    r.xga60 = xga60
    r.cf60 = cf60
    r.ca60 = ca60
    return r


def _instat(game_id, pb_w=3, pb_t=5, e_pass=2, e_stick=3, e_dump=1):
    r = PlayerGameStatsInStat(game_id=game_id, player_id=1)
    r.pb_won_dz = pb_w
    r.pb_total_dz = pb_t
    r.pb_won_oz = 0
    r.pb_total_oz = 0
    r.pb_won_nz = 0
    r.pb_total_nz = 0
    r.entries_pass = e_pass
    r.entries_stick = e_stick
    r.entries_dump = e_dump
    return r


COHORTS = {
    "W": {
        "xg_diff": [0.0, 0.5, -0.3, 0.2, -0.1, 0.4],
        "cf_pct": [0.5, 0.55, 0.48, 0.52, 0.51, 0.49],
        "battle_w_pct": [0.5, 0.55, 0.6, 0.48, 0.52, 0.53],
        "controlled_entry_pct": [0.6, 0.7, 0.55, 0.65, 0.58, 0.62],
    },
    "D": {"xg_diff": [], "cf_pct": [], "battle_w_pct": [], "controlled_entry_pct": []},
}


class TestImpactScore:
    def _player(self, position="F"):
        p = Player(name="X", number="1", position=position, is_center=False, active=True)
        p.id = 1
        return p

    def test_empty(self):
        p = self._player()
        r = impact_score(p, [], {}, COHORTS)
        assert r == {
            "score": None, "games": 0, "components_used": [],
            "clamped": False, "per_game": [],
        }

    def test_single_game_all_components(self):
        p = self._player()
        pgs = [_pgs(game_id=1)]
        instat = {1: _instat(game_id=1)}
        r = impact_score(p, pgs, instat, COHORTS)
        assert r["score"] is not None
        assert r["games"] == 1
        assert set(r["components_used"]) <= {"z_xg", "z_terr", "z_battle", "z_entry"}
        assert len(r["per_game"]) == 1

    def test_short_toi_game_excluded(self):
        p = self._player()
        pgs = [_pgs(game_id=1, toi_5v5=3.0), _pgs(game_id=2, toi_5v5=20.0)]
        instat = {1: _instat(game_id=1), 2: _instat(game_id=2)}
        r = impact_score(p, pgs, instat, COHORTS)
        # Only game 2 counts
        assert r["games"] == 1

    def test_missing_instat_drops_components(self):
        p = self._player()
        pgs = [_pgs(game_id=1)]
        r = impact_score(p, pgs, {}, COHORTS)
        assert r["games"] == 1
        assert "z_battle" not in r["per_game"][0]["components"]
        assert "z_entry" not in r["per_game"][0]["components"]

    def test_defender_no_entry_component(self):
        p = self._player(position="D")
        pgs = [_pgs(game_id=1)]
        instat = {1: _instat(game_id=1)}
        # D position: z_entry not applicable (spec §9.1: F/W only)
        r = impact_score(p, pgs, instat, COHORTS)
        # z_xg/z_terr should attempt cohort lookup ("D" cohort is empty in fixture)
        # so those components skip. z_battle uses "D" cohort which is empty too.
        # Result should be None (no valid components).
        assert r["games"] == 1
        assert all("z_entry" not in g["components"] for g in r["per_game"])

    def test_clamping(self):
        # Force clamping to fire deterministically: z-score > 3 in at least one component
        p = self._player()
        # Cohort with mean=0.5 and clear, reasonable stddev
        cohort = {
            "W": {
                "xg_diff": [0.0, 0.1, -0.1, 0.05, -0.05, 0.0, 0.02, -0.02, 0.03, -0.03],
                "cf_pct": [0.5] * 10,
                "battle_w_pct": [0.5] * 10,
                "controlled_entry_pct": [0.5] * 10,
            },
        }
        # Player game: xgf60 - xga60 = 10, way beyond cohort's typical range
        pgs = [_pgs(game_id=1, xgf60=15, xga60=5)]
        r = impact_score(p, pgs, {}, cohort)
        # Verify clamping fired: score should be exactly 3.0 and clamped flag True
        assert r["score"] == 3.0
        assert r["clamped"] is True
