import pytest
from app.flags import Rule, Flag, evaluate_rule, toi_weighted_stats, evaluate_toi_trend, evaluate_toi_outliers


def _trend(*points):
    """Helper: each arg is (date_iso, toi, stat_value) → dict."""
    return [
        {"game_id": i + 1, "date": d, "toi_5v5": toi, "cf60": v}
        for i, (d, toi, v) in enumerate(points)
    ]


class TestToiWeightedStats:
    def test_empty_returns_zero_n(self):
        b = toi_weighted_stats([], "cf60")
        assert b == {"mean": None, "std": None, "n": 0}

    def test_ignores_games_under_5_min_toi(self):
        t = _trend(
            ("2025-10-01", 20.0, 60.0),
            ("2025-10-05", 3.0, 100.0),  # excluded, TOI < 5
            ("2025-10-09", 15.0, 40.0),
        )
        b = toi_weighted_stats(t, "cf60")
        assert b["n"] == 2

    def test_computes_toi_weighted_mean(self):
        t = _trend(
            ("2025-10-01", 20.0, 60.0),
            ("2025-10-05", 10.0, 30.0),
        )
        # weighted = (60*20 + 30*10) / 30 = 50
        b = toi_weighted_stats(t, "cf60")
        assert b["mean"] == pytest.approx(50.0, abs=1e-9)

    def test_ignores_none_values(self):
        t = _trend(
            ("2025-10-01", 20.0, 60.0),
            ("2025-10-05", 15.0, None),
            ("2025-10-09", 10.0, 40.0),
        )
        b = toi_weighted_stats(t, "cf60")
        assert b["n"] == 2


class TestEvaluateRule:
    def _mk_trend(self, cf60_values):
        return [
            {"game_id": i + 1, "date": f"2025-10-{i+1:02d}", "toi_5v5": 15.0, "cf60": v}
            for i, v in enumerate(cf60_values)
        ]

    def test_returns_none_when_baseline_history_insufficient(self):
        rule = Rule("cf60", window=3, baseline=10, z_threshold=1.0, label="test")
        trend = self._mk_trend([50.0, 55.0, 60.0])  # only 3 games
        assert evaluate_rule(rule, trend) is None

    def test_returns_none_when_z_below_threshold(self):
        rule = Rule("cf60", window=3, baseline=10, z_threshold=1.0, label="test")
        # baseline all 50, window all 50 → z = 0
        trend = self._mk_trend([50.0] * 10)
        assert evaluate_rule(rule, trend) is None

    def test_returns_flag_when_window_much_higher(self):
        rule = Rule("cf60", window=3, baseline=10, z_threshold=1.0, label="Corsi shift")
        # baseline ~50 with variance, window jumps to 80
        trend = self._mk_trend([45.0, 55.0, 48.0, 52.0, 47.0, 53.0, 50.0, 80.0, 80.0, 80.0])
        flag = evaluate_rule(rule, trend)
        assert flag is not None
        assert flag.direction == "up"
        assert flag.z_score > 1.0
        assert flag.label == "Corsi shift"

    def test_returns_flag_when_window_much_lower(self):
        rule = Rule("cf60", window=3, baseline=10, z_threshold=1.0, label="Corsi shift")
        trend = self._mk_trend([50.0, 55.0, 48.0, 52.0, 47.0, 53.0, 51.0, 20.0, 20.0, 20.0])
        flag = evaluate_rule(rule, trend)
        assert flag is not None
        assert flag.direction == "down"
        assert flag.z_score < -1.0

    def test_baseline_uses_last_N_games_not_all(self):
        rule = Rule("cf60", window=3, baseline=5, z_threshold=1.0, label="test")
        # 8 games total; baseline should use last 5 (not include the first 3 wild values)
        trend = self._mk_trend([100.0, 100.0, 100.0, 50.0, 50.0, 50.0, 50.0, 50.0])
        # last 5 all 50 → std = 0 → cannot compute z → None
        assert evaluate_rule(rule, trend) is None


def _toi_trend(toi_values):
    return [
        {"game_id": i + 1, "date": f"2025-10-{i+1:02d}", "toi_5v5": v, "cf60": 50.0}
        for i, v in enumerate(toi_values)
    ]


class TestEvaluateToiTrend:
    def test_returns_none_when_under_10_games(self):
        assert evaluate_toi_trend(_toi_trend([15.0] * 5)) is None

    def test_returns_none_when_trend_within_10_pct(self):
        # all 15 min TOI → no shift
        assert evaluate_toi_trend(_toi_trend([15.0] * 10)) is None

    def test_flags_trending_up(self):
        # L10 mean = ~15, L3 mean = 20 → +33%
        trend = _toi_trend([15, 15, 15, 15, 15, 15, 15, 20, 20, 20])
        flag = evaluate_toi_trend(trend)
        assert flag is not None
        assert flag.direction == "up"
        assert flag.label == "TOI shift"

    def test_flags_trending_down(self):
        trend = _toi_trend([15, 15, 15, 15, 15, 15, 15, 8, 8, 8])
        flag = evaluate_toi_trend(trend)
        assert flag is not None
        assert flag.direction == "down"

    def test_does_not_flag_9_pct_shift(self):
        # L10 mean = ~15.4, L3 = 16.7 → +8.4%
        trend = _toi_trend([15, 15, 15, 15, 15, 15, 15, 17, 16, 17])
        assert evaluate_toi_trend(trend) is None


class TestEvaluateToiOutliers:
    def test_returns_empty_when_under_10_games(self):
        assert evaluate_toi_outliers(_toi_trend([15.0] * 5)) == []

    def test_flags_reduced_role_game(self):
        # L10 (games 1-10) mean = 15; game 11 = 5 (33%) → reduced role
        trend = _toi_trend([15.0] * 10 + [5.0])
        flags = evaluate_toi_outliers(trend)
        # first 10 games have no L10 baseline for themselves, but game 11 does
        reduced = [f for f in flags if f.label == "reduced role"]
        assert len(reduced) == 1
        assert reduced[0].game_id == 11

    def test_flags_expanded_role_game(self):
        trend = _toi_trend([12.0] * 10 + [22.0])
        # game 11: 22 / 12 = 1.83 > 1.5
        flags = evaluate_toi_outliers(trend)
        expanded = [f for f in flags if f.label == "expanded role"]
        assert len(expanded) == 1
        assert expanded[0].game_id == 11

    def test_does_not_flag_normal_game(self):
        trend = _toi_trend([15.0] * 10 + [14.0])  # 93% of L10
        flags = evaluate_toi_outliers(trend)
        assert flags == []
