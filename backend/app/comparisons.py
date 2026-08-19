from typing import Optional
from .models import Player
from .cohorts import cohort_matches, cohort_baseline


COMPARISON_COHORTS: dict[str, str] = {
    "toi_5v5": "F",
    "on_ice_cf_pct": "F",
    "on_ice_xgf_pct": "F",
    "on_ice_sf_pct": "F",
    "cf60": "F",
    "ca60": "F",
    "ff60": "F",
    "fa60": "F",
    "sf60": "F",
    "sa60": "F",
    "xfsh_pct": "F",
    "xfsv_pct": "F",
    "icf": "F",
    "isf": "F",
    "median_shift_seconds": "F",
    "personal_fo_pct": "C",
    "on_ice_fo_pct": "C",
}

# Per-cohort override: defenders compared to defenders for these stats
DEFENDER_STATS = {
    "on_ice_cf_pct", "on_ice_xgf_pct", "on_ice_sf_pct",
    "cf60", "ca60", "ff60", "fa60", "sf60", "sa60",
    "xfsh_pct", "xfsv_pct", "toi_5v5", "median_shift_seconds",
}

# Direction: True = higher is better
HIGHER_IS_BETTER: dict[str, bool] = {
    "toi_5v5": True,
    "on_ice_cf_pct": True,
    "on_ice_xgf_pct": True,
    "on_ice_sf_pct": True,
    "cf60": True,
    "ca60": False,
    "ff60": True,
    "fa60": False,
    "sf60": True,
    "sa60": False,
    "xfsh_pct": True,
    "xfsv_pct": True,
    "icf": True,
    "isf": True,
    "median_shift_seconds": True,
    "personal_fo_pct": True,
    "on_ice_fo_pct": True,
}


def _cohort_for(target: Player, stat: str) -> str:
    """Choose comparison cohort for target player's stat.

    Defenders always compare to D. Faceoff stats use C. Otherwise F.
    """
    if target.position == "D" and stat in DEFENDER_STATS:
        return "D"
    if target.position == "G":
        return "G"
    return COMPARISON_COHORTS.get(stat, "F")


def _delta(target_val: float, baseline_mean: Optional[float]) -> Optional[float]:
    if target_val is None or baseline_mean is None:
        return None
    return target_val - baseline_mean


def _indicator(
    target_val: Optional[float],
    team_mean: Optional[float],
    position_mean: Optional[float],
    higher_is_better: bool,
) -> str:
    """Green if above both baselines (or below both for lower-is-better)."""
    if target_val is None:
        return "neutral"
    beats_team = _beats(target_val, team_mean, higher_is_better)
    beats_pos = _beats(target_val, position_mean, higher_is_better)
    trues = sum(1 for x in (beats_team, beats_pos) if x is True)
    falses = sum(1 for x in (beats_team, beats_pos) if x is False)
    if beats_team is None and beats_pos is None:
        return "neutral"
    if trues == 2:
        return "green"
    if trues == 1:
        return "yellow"
    if falses >= 1:
        return "red"
    return "neutral"


def _beats(val: Optional[float], baseline: Optional[float], higher_is_better: bool) -> Optional[bool]:
    if val is None or baseline is None:
        return None
    return (val > baseline) if higher_is_better else (val < baseline)


def build_comparisons(
    target: Player,
    target_aggs: dict,
    all_player_aggs: list[tuple[Player, dict]],
) -> dict:
    """For each stat in target_aggs, compute team + position baselines and colored indicator."""
    result: dict = {}
    for stat_key in COMPARISON_COHORTS:
        target_val = target_aggs.get(stat_key)
        # team baseline: everyone with a value for this stat, TOI-weighted where applicable
        team_values = [agg.get(stat_key) for _, agg in all_player_aggs]
        team_weights = [agg.get("toi_5v5") or 0 for _, agg in all_player_aggs]
        team = cohort_baseline(team_values, team_weights)

        cohort = _cohort_for(target, stat_key)
        pos_values = [
            agg.get(stat_key)
            for p, agg in all_player_aggs
            if cohort_matches(p, cohort)
        ]
        pos_weights = [
            agg.get("toi_5v5") or 0
            for p, agg in all_player_aggs
            if cohort_matches(p, cohort)
        ]
        position = cohort_baseline(pos_values, pos_weights)

        higher_better = HIGHER_IS_BETTER.get(stat_key, True)
        result[stat_key] = {
            "value": target_val,
            "cohort": cohort,
            "team_baseline": team,
            "position_baseline": position,
            "team_delta": _delta(target_val, team["mean"]),
            "position_delta": _delta(target_val, position["mean"]),
            "indicator": _indicator(target_val, team["mean"], position["mean"], higher_better),
        }
    return result
