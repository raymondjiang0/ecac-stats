"""Shared helper for enriching a player's aggregate stats with
comparisons, flags, and per-game flags. Used by both the stats API
and the PDF report generator so behavior stays consistent."""
from dataclasses import asdict
from .models import Player
from .comparisons import build_comparisons
from .flags import evaluate_rule, evaluate_toi_trend, evaluate_toi_outliers
from .flag_rules import DEFAULT_FLAG_RULES
from .calculations import top_flags


def enrich_player_agg(
    player: Player,
    agg: dict,
    all_aggs: list[tuple[Player, dict]],
) -> dict:
    """Attach comparisons/flags/game_flags to a player aggregate in-place.
    Returns the same dict for chaining."""
    agg["comparisons"] = build_comparisons(player, agg, all_aggs)

    trend = agg.get("trend", [])
    rolling = [evaluate_rule(r, trend) for r in DEFAULT_FLAG_RULES]
    rolling = [f for f in rolling if f is not None]
    toi_f = evaluate_toi_trend(trend)
    if toi_f is not None:
        rolling.append(toi_f)
    agg["flags"] = [asdict(f) for f in top_flags(rolling, n=3)]

    game_flags: dict[int, list] = {}
    for f in evaluate_toi_outliers(trend):
        if f.game_id is None:
            continue
        game_flags.setdefault(f.game_id, []).append(asdict(f))
    agg["game_flags"] = game_flags

    return agg
