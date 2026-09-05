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


from datetime import date as _date
from sqlalchemy.orm import Session
from typing import Optional as _Optional
from .models import PlayerGameStatsInStat, TeamGameStatsInStat, Game


def load_player_instat_rows(
    db: Session,
    player_id: int,
    date_from: _Optional[_date] = None,
    date_to: _Optional[_date] = None,
) -> list[PlayerGameStatsInStat]:
    """Load PlayerGameStatsInStat rows for a player, optionally filtered by
    game date range. Returns [] if the player has no rows."""
    q = db.query(PlayerGameStatsInStat).join(Game).filter(
        PlayerGameStatsInStat.player_id == player_id
    )
    if date_from is not None:
        q = q.filter(Game.date >= date_from)
    if date_to is not None:
        q = q.filter(Game.date <= date_to)
    return q.all()


def load_team_instat_rows(
    db: Session,
    date_from: _Optional[_date] = None,
    date_to: _Optional[_date] = None,
) -> list[TeamGameStatsInStat]:
    """Load TeamGameStatsInStat rows, optionally filtered by game date range."""
    q = db.query(TeamGameStatsInStat).join(Game)
    if date_from is not None:
        q = q.filter(Game.date >= date_from)
    if date_to is not None:
        q = q.filter(Game.date <= date_to)
    return q.all()
