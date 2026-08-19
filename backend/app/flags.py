from dataclasses import dataclass, field
from typing import Optional


MIN_TOI_MINUTES = 5.0  # games below this are excluded from all flag computation


@dataclass(frozen=True)
class Rule:
    stat_key: str
    window: int
    baseline: int
    z_threshold: float
    label: str


@dataclass
class Flag:
    kind: str          # "trend" or "outlier"
    label: str
    direction: str     # "up" or "down"
    z_score: Optional[float]
    window_value: Optional[float]
    baseline_value: Optional[float]
    game_id: Optional[int] = None


def toi_weighted_stats(trend: list[dict], stat_key: str) -> dict:
    """Return TOI-weighted mean and stddev of stat_key across trend.

    Games with toi_5v5 < MIN_TOI_MINUTES or None values are excluded.
    Returns {"mean": None, "std": None, "n": 0} for empty or single-value sets.
    """
    values = []
    weights = []
    for pt in trend:
        toi = pt.get("toi_5v5")
        val = pt.get(stat_key)
        if toi is None or toi < MIN_TOI_MINUTES:
            continue
        if val is None:
            continue
        values.append(val)
        weights.append(toi)
    n = len(values)
    if n < 2:
        return {"mean": None, "std": None, "n": n}
    total_w = sum(weights)
    if total_w <= 0:
        return {"mean": None, "std": None, "n": n}
    mean = sum(v * w for v, w in zip(values, weights)) / total_w
    var = sum(w * (v - mean) ** 2 for v, w in zip(values, weights)) / total_w
    return {"mean": mean, "std": var ** 0.5, "n": n}


def evaluate_rule(rule: Rule, trend: list[dict]) -> Optional[Flag]:
    """Evaluate a rolling-window flag rule against a player's trend."""
    qualifying = [
        pt for pt in trend
        if pt.get("toi_5v5") is not None
        and pt["toi_5v5"] >= MIN_TOI_MINUTES
        and pt.get(rule.stat_key) is not None
    ]
    if len(qualifying) < rule.baseline:
        return None

    baseline_trend = qualifying[-rule.baseline:]
    window_trend = qualifying[-rule.window:]

    base = toi_weighted_stats(baseline_trend, rule.stat_key)
    win = toi_weighted_stats(window_trend, rule.stat_key)

    if base["mean"] is None or base["std"] is None or base["std"] == 0:
        return None
    if win["mean"] is None:
        return None

    z = (win["mean"] - base["mean"]) / base["std"]
    if abs(z) < rule.z_threshold:
        return None

    return Flag(
        kind="trend",
        label=rule.label,
        direction="up" if z > 0 else "down",
        z_score=z,
        window_value=win["mean"],
        baseline_value=base["mean"],
    )


TOI_TREND_THRESHOLD = 0.10  # ±10%
TOI_OUTLIER_LOW = 0.50
TOI_OUTLIER_HIGH = 1.50


def _mean_toi(trend_slice: list[dict]) -> Optional[float]:
    tois = [pt["toi_5v5"] for pt in trend_slice
            if pt.get("toi_5v5") is not None and pt["toi_5v5"] >= MIN_TOI_MINUTES]
    if not tois:
        return None
    return sum(tois) / len(tois)


def evaluate_toi_trend(trend: list[dict]) -> Optional[Flag]:
    """L3-vs-L10 TOI shift flag. Requires ≥10 qualifying games."""
    qualifying = [pt for pt in trend
                  if pt.get("toi_5v5") is not None and pt["toi_5v5"] >= MIN_TOI_MINUTES]
    if len(qualifying) < 10:
        return None
    l10_mean = _mean_toi(qualifying[-10:])
    l3_mean = _mean_toi(qualifying[-3:])
    if l10_mean is None or l3_mean is None or l10_mean == 0:
        return None
    pct_shift = (l3_mean - l10_mean) / l10_mean
    if abs(pct_shift) < TOI_TREND_THRESHOLD:
        return None
    return Flag(
        kind="trend",
        label="TOI shift",
        direction="up" if pct_shift > 0 else "down",
        z_score=None,
        window_value=l3_mean,
        baseline_value=l10_mean,
    )


def evaluate_toi_outliers(trend: list[dict]) -> list[Flag]:
    """Per-game outlier flags. Requires ≥10 qualifying prior games for each check."""
    qualifying = [pt for pt in trend
                  if pt.get("toi_5v5") is not None and pt["toi_5v5"] >= MIN_TOI_MINUTES]
    if len(qualifying) < 10:
        return []
    # Sort by game order preserved by trend list order (aggregate_player_stats sorts by date)
    flags: list[Flag] = []
    # Only games at position >= 10 (index) have a prior L10 baseline
    for i in range(10, len(qualifying)):
        prior_10 = qualifying[i - 10:i]
        baseline = _mean_toi(prior_10)
        game = qualifying[i]
        toi = game["toi_5v5"]
        if baseline is None or baseline == 0 or toi is None:
            continue
        ratio = toi / baseline
        if ratio < TOI_OUTLIER_LOW:
            flags.append(Flag(
                kind="outlier",
                label="reduced role",
                direction="down",
                z_score=None,
                window_value=toi,
                baseline_value=baseline,
                game_id=game["game_id"],
            ))
        elif ratio > TOI_OUTLIER_HIGH:
            flags.append(Flag(
                kind="outlier",
                label="expanded role",
                direction="up",
                z_score=None,
                window_value=toi,
                baseline_value=baseline,
                game_id=game["game_id"],
            ))
    return flags
