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
    all_aggs: list,
    *,
    instat_rows: list = None,
    team_instat_rows: list = None,
    pgs_rows: list = None,
    position_cohorts: dict = None,
) -> dict:
    """Attach comparisons/flags/game_flags (Phase 1) and Tier 2 stats
    (Phase 3) to a player aggregate in-place. Returns the same dict.

    Phase 1 layers always run. Tier 2 layers run only when InStat rows are
    provided — passing None (or omitting) preserves pre-Phase-3 behavior.
    """
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

    # Phase 3: Tier 2 stats
    if instat_rows is not None:
        from .tier2_stats import (
            contested_puck_win_pct, zone_entry_composition,
            turnover_location_ratio, danger_zone_shot_share, impact_score,
        )
        agg["contested_puck"] = contested_puck_win_pct(instat_rows)
        agg["zone_entry"] = zone_entry_composition(instat_rows)
        agg["turnover_ratio"] = turnover_location_ratio(instat_rows)
        agg["danger_share"] = danger_zone_shot_share(
            instat_rows, team_instat_rows or [], pgs_rows or [],
        )
        instat_by_game = {r.game_id: r for r in instat_rows}
        agg["impact_score"] = impact_score(
            player, pgs_rows or [], instat_by_game, position_cohorts or {},
        )

    return agg


from datetime import date as _date
from sqlalchemy.orm import Session
from typing import Optional as _Optional
from .models import PlayerGameStats, PlayerGameStatsInStat, TeamGameStatsInStat, Game


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


def build_position_cohorts(
    all_players,
    db: Session,
    date_from: _Optional[_date] = None,
    date_to: _Optional[_date] = None,
) -> dict:
    """Build per-position stat distributions for Impact Score z-scoring.

    Used by both stats and reports routers so cohort computation stays
    consistent. Returns a dict mapping position group -> {stat_key: [values]}.
    """
    cohorts: dict = {}
    for p in all_players:
        pos = p.position or "F"
        if pos not in cohorts:
            cohorts[pos] = {
                "xg_diff": [],
                "cf_pct": [],
                "battle_w_pct": [],
                "controlled_entry_pct": [],
            }
        pgs_q = db.query(PlayerGameStats).join(Game).filter(
            PlayerGameStats.player_id == p.id
        )
        if date_from:
            pgs_q = pgs_q.filter(Game.date >= date_from)
        if date_to:
            pgs_q = pgs_q.filter(Game.date <= date_to)
        for r in pgs_q.all():
            if r.toi_5v5 and r.toi_5v5 >= 5:
                if r.xgf60 is not None and r.xga60 is not None:
                    cohorts[pos]["xg_diff"].append(r.xgf60 - r.xga60)
                cf, ca = r.cf60 or 0, r.ca60 or 0
                if (cf + ca) > 0:
                    cohorts[pos]["cf_pct"].append(cf / (cf + ca))
        for ir in load_player_instat_rows(db, p.id, date_from, date_to):
            pb_w = (ir.pb_won_dz or 0) + (ir.pb_won_oz or 0) + (ir.pb_won_nz or 0)
            pb_t = (ir.pb_total_dz or 0) + (ir.pb_total_oz or 0) + (ir.pb_total_nz or 0)
            if pb_t > 0:
                cohorts[pos]["battle_w_pct"].append(pb_w / pb_t)
            p_e = ir.entries_pass or 0
            s_e = ir.entries_stick or 0
            d_e = ir.entries_dump or 0
            tot_e = p_e + s_e + d_e
            if tot_e > 0:
                cohorts[pos]["controlled_entry_pct"].append((p_e + s_e) / tot_e)
    return cohorts
