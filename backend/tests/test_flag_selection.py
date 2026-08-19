from app.flags import Flag
from app.calculations import top_flags


def _flag(z, label="test"):
    return Flag(kind="trend", label=label, direction="up",
                z_score=z, window_value=None, baseline_value=None)


class TestTopFlags:
    def test_returns_all_when_fewer_than_n(self):
        flags = [_flag(1.5), _flag(-2.0)]
        assert len(top_flags(flags, n=3)) == 2

    def test_sorts_by_absolute_z_descending(self):
        flags = [_flag(1.5, "small"), _flag(-3.0, "big"), _flag(2.0, "mid")]
        result = top_flags(flags, n=3)
        assert [f.label for f in result] == ["big", "mid", "small"]

    def test_caps_at_n(self):
        flags = [_flag(z) for z in [1.5, -2.0, 3.0, -1.8, 2.5]]
        assert len(top_flags(flags, n=3)) == 3

    def test_none_z_scores_go_last(self):
        f_none = Flag(kind="trend", label="none-z", direction="up",
                      z_score=None, window_value=None, baseline_value=None)
        flags = [_flag(1.5), f_none, _flag(2.5)]
        result = top_flags(flags, n=3)
        assert result[-1].label == "none-z"
