import pytest
from app.models import Player
from app.cohorts import position_group, cohort_matches, cohort_baseline


class TestPositionGroup:
    def test_forward_non_center_returns_F(self):
        p = Player(name="x", position="F", is_center=False)
        assert position_group(p) == "W"

    def test_forward_center_returns_C(self):
        p = Player(name="x", position="F", is_center=True)
        assert position_group(p) == "C"

    def test_defender_returns_D(self):
        p = Player(name="x", position="D", is_center=False)
        assert position_group(p) == "D"

    def test_goalie_returns_G(self):
        p = Player(name="x", position="G", is_center=False)
        assert position_group(p) == "G"


class TestCohortMatches:
    def test_F_matches_center(self):
        p = Player(name="x", position="F", is_center=True)
        assert cohort_matches(p, "F") is True

    def test_F_matches_winger(self):
        p = Player(name="x", position="F", is_center=False)
        assert cohort_matches(p, "F") is True

    def test_F_does_not_match_defender(self):
        p = Player(name="x", position="D", is_center=False)
        assert cohort_matches(p, "F") is False

    def test_C_matches_only_center(self):
        c = Player(name="x", position="F", is_center=True)
        w = Player(name="y", position="F", is_center=False)
        assert cohort_matches(c, "C") is True
        assert cohort_matches(w, "C") is False

    def test_D_matches_only_defender(self):
        f = Player(name="x", position="F", is_center=False)
        d = Player(name="y", position="D", is_center=False)
        assert cohort_matches(d, "D") is True
        assert cohort_matches(f, "D") is False


class TestCohortBaseline:
    def test_returns_none_for_empty(self):
        b = cohort_baseline([])
        assert b == {"mean": None, "std": None, "n": 0}

    def test_returns_none_for_single_value(self):
        b = cohort_baseline([0.5])
        assert b["mean"] is None
        assert b["std"] is None
        assert b["n"] == 1

    def test_unweighted_mean_and_std(self):
        b = cohort_baseline([0.4, 0.5, 0.6])
        assert b["mean"] == pytest.approx(0.5, abs=1e-9)
        assert b["std"] == pytest.approx(0.0816496, abs=1e-4)
        assert b["n"] == 3

    def test_weighted_mean(self):
        b = cohort_baseline([1.0, 3.0], weights=[1.0, 3.0])
        # weighted mean = (1*1 + 3*3) / 4 = 2.5
        assert b["mean"] == pytest.approx(2.5, abs=1e-9)

    def test_ignores_none_values(self):
        b = cohort_baseline([0.4, None, 0.6, None])
        assert b["mean"] == pytest.approx(0.5, abs=1e-9)
        assert b["n"] == 2

    def test_zero_total_weight_returns_none(self):
        b = cohort_baseline([1.0, 2.0], weights=[0.0, 0.0])
        assert b["mean"] is None
        assert b["std"] is None
