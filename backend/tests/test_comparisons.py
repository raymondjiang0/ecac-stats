import pytest
from app.models import Player
from app.comparisons import build_comparisons, COMPARISON_COHORTS, HIGHER_IS_BETTER


def _mk_player(name, pos, is_center=False):
    return Player(name=name, position=pos, is_center=is_center, active=True)


def _mk_agg(cf60=None, ca60=None, xfsh_pct=None, personal_fo_pct=None, toi=100.0):
    return {
        "toi_5v5": toi,
        "cf60": cf60,
        "ca60": ca60,
        "xfsh_pct": xfsh_pct,
        "personal_fo_pct": personal_fo_pct,
    }


class TestBuildComparisons:
    def test_returns_dict_keyed_by_stat_name(self):
        target = _mk_player("target", "F")
        other = _mk_player("other", "F")
        target_agg = _mk_agg(cf60=60.0)
        result = build_comparisons(
            target, target_agg, [(target, target_agg), (other, _mk_agg(cf60=50.0))]
        )
        assert "cf60" in result

    def test_team_delta_computed_from_all_players(self):
        target = _mk_player("target", "F")
        p2 = _mk_player("p2", "F")
        p3 = _mk_player("p3", "D")
        aggs = [
            (target, _mk_agg(cf60=60.0)),
            (p2, _mk_agg(cf60=40.0)),
            (p3, _mk_agg(cf60=50.0)),
        ]
        result = build_comparisons(target, _mk_agg(cf60=60.0), aggs)
        # team mean = 50, delta = 10
        assert result["cf60"]["team_delta"] == pytest.approx(10.0, abs=1e-9)

    def test_position_delta_uses_cohort_from_config(self):
        target = _mk_player("target", "F")
        p2 = _mk_player("p2", "F")
        d1 = _mk_player("d1", "D")
        d2 = _mk_player("d2", "D")
        aggs = [
            (target, _mk_agg(cf60=60.0)),
            (p2, _mk_agg(cf60=40.0)),
            (d1, _mk_agg(cf60=30.0)),
            (d2, _mk_agg(cf60=30.0)),
        ]
        # cf60 cohort is "F" — position mean = (60+40)/2 = 50, delta = 10
        result = build_comparisons(target, _mk_agg(cf60=60.0), aggs)
        assert result["cf60"]["position_delta"] == pytest.approx(10.0, abs=1e-9)

    def test_higher_is_better_gives_green_when_above_both(self):
        target = _mk_player("target", "F")
        p2 = _mk_player("p2", "F")
        d1 = _mk_player("d1", "D")
        aggs = [
            (target, _mk_agg(cf60=70.0)),
            (p2, _mk_agg(cf60=40.0)),
            (d1, _mk_agg(cf60=30.0)),
        ]
        result = build_comparisons(target, _mk_agg(cf60=70.0), aggs)
        assert result["cf60"]["indicator"] == "green"

    def test_lower_is_better_gives_green_when_below_both(self):
        # ca60 = lower is better
        target = _mk_player("target", "F")
        p2 = _mk_player("p2", "F")
        aggs = [
            (target, _mk_agg(ca60=20.0)),
            (p2, _mk_agg(ca60=40.0)),
        ]
        result = build_comparisons(target, _mk_agg(ca60=20.0), aggs)
        assert result["ca60"]["indicator"] == "green"

    def test_faceoff_stat_compares_to_centers_only(self):
        center = _mk_player("c", "F", is_center=True)
        winger = _mk_player("w", "F", is_center=False)
        aggs = [
            (center, _mk_agg(personal_fo_pct=0.60)),
            (winger, _mk_agg(personal_fo_pct=0.40)),
        ]
        # personal_fo_pct cohort = "C" → position baseline uses only centers
        # only one center → position_baseline mean/std should be None (n<2)
        result = build_comparisons(center, _mk_agg(personal_fo_pct=0.60), aggs)
        assert result["personal_fo_pct"]["position_baseline"]["n"] == 1
        assert result["personal_fo_pct"]["position_baseline"]["mean"] is None
