from typing import Optional
from datetime import date

from .stat_sources import STAT_SOURCES, games_with_stat


def _sources_for(g_source: str, declared: set) -> set:
    """Compute which source label(s) apply for a single game and stat.

    A game tagged "both" supplies data from either source; intersect with
    the stat's declared set so we label only what is actually used.
    """
    if g_source == "both":
        return {"49ing", "instat"} & declared
    return {g_source} & declared


def _availability_for(games: list, stat_keys: list, rows_by_game_id: dict) -> dict:
    """Build the per-stat availability metadata block.

    games: the game set for the window (filtered by date range at the router).
    stat_keys: which stat_keys to report on.
    rows_by_game_id: mapping game_id → row (the data-holding row; PlayerGameStats
    for player aggregation, TeamGameStats for team). Presence indicates a row exists.
    """
    out = {}
    for key in stat_keys:
        eligible = games_with_stat(games, key)
        # Restrict to games that actually have a data row loaded (empty stats
        # rows exist for backfilled games; we still count them because the
        # user entered them as 49ing games, i.e. data intentionally missing is
        # different from source-unsupported).
        eligible_with_rows = [g for g in eligible if g.id in rows_by_game_id]
        counted = len(eligible_with_rows)
        declared = STAT_SOURCES.get(key, set())
        sources_seen: set = set()
        for g in eligible_with_rows:
            sources_seen |= _sources_for(g.data_source, declared)
        out[key] = {"games": counted, "sources": sorted(sources_seen)}
    return out


def safe_div(numerator: Optional[float], denominator: Optional[float]) -> Optional[float]:
    if numerator is None or denominator is None:
        return None
    if denominator == 0:
        return None
    return numerator / denominator


def pct(numerator: Optional[float], denominator: Optional[float]) -> Optional[float]:
    """Percentage share: numerator / (numerator + denominator)."""
    if numerator is None or denominator is None:
        return None
    total = numerator + denominator
    if total == 0:
        return None
    return numerator / total


def per60(count: Optional[float], toi_minutes: Optional[float]) -> Optional[float]:
    if count is None or toi_minutes is None or toi_minutes == 0:
        return None
    return (count / toi_minutes) * 60


# ── Team per-game stats ───────────────────────────────────────────────────────

def estimated_5v5_toi(tgs) -> Optional[float]:
    """5v5 TOI = total game time − PP TOI − PK TOI − other strength states."""
    total = tgs.total_game_time
    if total is None:
        return None
    pp = tgs.toi_pp or 0
    pk = tgs.toi_pk or 0
    other = tgs.other_toi or 0
    result = total - pp - pk - other
    return max(result, 0)


def team_game_stats(tgs) -> dict:
    """Compute derived stats from a single TeamGameStats row."""
    toi = estimated_5v5_toi(tgs)
    return {
        "cf_pct": pct(tgs.cf_for_5v5, tgs.cf_against_5v5),
        "xgf_pct": pct(tgs.xgf_5v5, tgs.xga_5v5),
        "xgf60": per60(tgs.xgf_5v5, toi),
        "xga60": per60(tgs.xga_5v5, toi),
        "pp_cf_pct": pct(tgs.cf_for_5v4, tgs.cf_against_5v4),
        "pp_xgf_pct": pct(tgs.xgf_5v4, tgs.xga_5v4),
        "pk_cf_pct": pct(tgs.cf_for_4v5, tgs.cf_against_4v5),
        "pk_xgf_pct": pct(tgs.xgf_4v5, tgs.xga_4v5),
    }


def attack_scenario_shares(tgs) -> dict:
    """
    Attack Scenario Mix by expected-goal share.
    49ing's Attack Scenarios tab only exposes xG totals per scenario, not shot counts.
    Mix = each scenario's xGF ÷ total scenario xGF (xG-weighted, not frequency-weighted).
    """
    rush = tgs.rush_xgf or 0
    fc = tgs.oz_fc_xgf or 0
    fo = tgs.oz_fo_xgf or 0
    sp = tgs.sust_pos_xgf or 0
    total = rush + fc + fo + sp
    if total == 0:
        return {"rush": None, "oz_fc": None, "oz_fo": None, "sust_pos": None}
    return {
        "rush": rush / total,
        "oz_fc": fc / total,
        "oz_fo": fo / total,
        "sust_pos": sp / total,
    }


# ── Aggregate team stats ──────────────────────────────────────────────────────

def aggregate_team_stats(team_stats_rows: list, games: list) -> dict:
    """Aggregate TeamGameStats rows across all games into season totals."""
    team_stat_keys = [
        "cf_pct", "xgf_pct", "xgf60", "xga60",
        "pp_cf_pct", "pp_xgf_pct", "pk_cf_pct", "pk_xgf_pct",
        "rush_share", "oz_fc_share", "oz_fo_share", "sust_pos_share",
    ]
    if not team_stats_rows:
        result = _empty_team_agg()
        rows_by_game_id: dict = {}
        result["availability"] = _availability_for(games, team_stat_keys, rows_by_game_id)
        return result

    cf_for = cf_ag = ff_for = ff_ag = xgf = xga = toi = 0.0
    cf_for_5v4 = cf_ag_5v4 = xgf_5v4 = xga_5v4 = 0.0
    cf_for_4v5 = cf_ag_4v5 = xgf_4v5 = xga_4v5 = 0.0
    rush_f = fc_f = fo_f = sp_f = 0.0
    cf_pct_trend = []
    xgf_pct_trend = []

    game_map = {g.id: g for g in games}

    for tgs in team_stats_rows:
        g = game_map.get(tgs.game_id)
        g_date = g.date if g else None
        g_opp = g.opponent if g else "?"

        cf_for += tgs.cf_for_5v5 or 0
        cf_ag += tgs.cf_against_5v5 or 0
        ff_for += tgs.ff_for_5v5 or 0
        ff_ag += tgs.ff_against_5v5 or 0
        xgf += tgs.xgf_5v5 or 0
        xga += tgs.xga_5v5 or 0
        toi += estimated_5v5_toi(tgs) or 0

        cf_for_5v4 += tgs.cf_for_5v4 or 0
        cf_ag_5v4 += tgs.cf_against_5v4 or 0
        xgf_5v4 += tgs.xgf_5v4 or 0
        xga_5v4 += tgs.xga_5v4 or 0

        cf_for_4v5 += tgs.cf_for_4v5 or 0
        cf_ag_4v5 += tgs.cf_against_4v5 or 0
        xgf_4v5 += tgs.xgf_4v5 or 0
        xga_4v5 += tgs.xga_4v5 or 0

        rush_f += tgs.rush_xgf or 0
        fc_f += tgs.oz_fc_xgf or 0
        fo_f += tgs.oz_fo_xgf or 0
        sp_f += tgs.sust_pos_xgf or 0

        cf_pct_trend.append({
            "game_id": tgs.game_id,
            "date": str(g_date) if g_date else None,
            "opponent": g_opp,
            "value": pct(tgs.cf_for_5v5, tgs.cf_against_5v5),
        })
        xgf_pct_trend.append({
            "game_id": tgs.game_id,
            "date": str(g_date) if g_date else None,
            "opponent": g_opp,
            "value": pct(tgs.xgf_5v5, tgs.xga_5v5),
        })

    total_attack = rush_f + fc_f + fo_f + sp_f

    result = {
        "games_logged": len(team_stats_rows),
        "cf_pct": pct(cf_for, cf_ag),
        "xgf_pct": pct(xgf, xga),
        "xgf60": per60(xgf, toi),
        "xga60": per60(xga, toi),
        "pp_cf_pct": pct(cf_for_5v4, cf_ag_5v4),
        "pp_xgf_pct": pct(xgf_5v4, xga_5v4),
        "pk_cf_pct": pct(cf_for_4v5, cf_ag_4v5),
        "pk_xgf_pct": pct(xgf_4v5, xga_4v5),
        "rush_share": safe_div(rush_f, total_attack),
        "oz_fc_share": safe_div(fc_f, total_attack),
        "oz_fo_share": safe_div(fo_f, total_attack),
        "sust_pos_share": safe_div(sp_f, total_attack),
        "cf_pct_trend": cf_pct_trend,
        "xgf_pct_trend": xgf_pct_trend,
    }
    rows_by_game_id = {r.game_id: r for r in team_stats_rows}
    result["availability"] = _availability_for(games, team_stat_keys, rows_by_game_id)
    return result


def _empty_team_agg() -> dict:
    return {
        "games_logged": 0,
        "cf_pct": None, "xgf_pct": None, "xgf60": None, "xga60": None,
        "pp_cf_pct": None, "pp_xgf_pct": None, "pk_cf_pct": None, "pk_xgf_pct": None,
        "rush_share": None, "oz_fc_share": None, "oz_fo_share": None, "sust_pos_share": None,
        "cf_pct_trend": [], "xgf_pct_trend": [],
    }


# ── Player per-game stats ─────────────────────────────────────────────────────

def player_game_stats(pgs, game) -> dict:
    """
    Per-game derived stats. All on-ice inputs are already per-60 (49ing scales them).
    CF% = CF60/(CF60+CA60) — TOI factors cancel, so pct() works directly on per-60 values.
    xFSh% = xGF60/FF60 — same cancellation logic.
    """
    xfsv_raw = safe_div(pgs.xga60, pgs.fa60)
    return {
        "game_id": game.id,
        "date": game.date,
        "opponent": game.opponent,
        "toi_5v5": pgs.toi_5v5,
        "on_ice_cf_pct": pct(pgs.cf60, pgs.ca60),
        "on_ice_xgf_pct": pct(pgs.xgf60, pgs.xga60),
        "on_ice_sf_pct": pct(pgs.sf60, pgs.sa60),
        "cf60": pgs.cf60,
        "ca60": pgs.ca60,
        "ff60": pgs.ff60,
        "fa60": pgs.fa60,
        "sf60": pgs.sf60,
        "sa60": pgs.sa60,
        "xfsh_pct": safe_div(pgs.xgf60, pgs.ff60),
        "xfsv_pct": (1 - xfsv_raw) if xfsv_raw is not None else None,
        "median_shift_seconds": pgs.median_shift_seconds,
        "personal_fo_pct": safe_div(pgs.personal_draws_won, pgs.personal_draws_taken),
        "on_ice_fo_pct": pct(pgs.team_fo_wins_on_ice, pgs.team_fo_losses_on_ice),
    }


# ── Aggregate player stats ────────────────────────────────────────────────────

def aggregate_player_stats(player, pgs_rows: list, games: list) -> dict:
    """Aggregate PlayerGameStats rows into season totals + per-game trend."""
    player_stat_keys = [
        "toi_5v5", "on_ice_cf_pct", "on_ice_xgf_pct", "on_ice_sf_pct",
        "cf60", "ca60", "ff60", "fa60", "sf60", "sa60",
        "xfsh_pct", "xfsv_pct", "icf", "isf",
        "median_shift_seconds", "personal_fo_pct", "on_ice_fo_pct",
    ]
    game_map = {g.id: g for g in games}
    games_with_toi = [r for r in pgs_rows if r.toi_5v5 and r.toi_5v5 > 0]
    games_played = len(games_with_toi)
    small_sample = games_played < 5

    if not games_with_toi:
        result = {
            "player_id": player.id,
            "player_name": player.name,
            "games_played": 0,
            "small_sample": True,
            "toi_5v5": None,
            "on_ice_cf_pct": None, "on_ice_xgf_pct": None, "on_ice_sf_pct": None,
            "cf60": None, "ca60": None, "ff60": None, "fa60": None,
            "sf60": None, "sa60": None,
            "xfsh_pct": None, "xfsv_pct": None,
            "icf": None, "isf": None,
            "median_shift_seconds": None,
            "personal_fo_pct": None, "on_ice_fo_pct": None,
            "trend": [],
        }
        rows_by_game_id = {r.game_id: r for r in pgs_rows}
        result["availability"] = _availability_for(games, player_stat_keys, rows_by_game_id)
        return result

    # Accumulate per-60 × TOI so season per-60 = sum / total_toi (TOI-weighted avg)
    cf_w = ca_w = ff_w = fa_w = sf_w = sa_w = xgf_w = xga_w = toi = 0.0
    personal_taken = personal_won = fo_wins = fo_losses = 0.0
    total_icf = total_isf = 0.0
    shift_seconds_list = []

    trend = []

    for pgs in sorted(pgs_rows, key=lambda r: game_map[r.game_id].date if r.game_id in game_map else date.min):
        g = game_map.get(pgs.game_id)
        if g is None:
            continue

        t = pgs.toi_5v5 or 0
        cf_w  += (pgs.cf60  or 0) * t
        ca_w  += (pgs.ca60  or 0) * t
        ff_w  += (pgs.ff60  or 0) * t
        fa_w  += (pgs.fa60  or 0) * t
        sf_w  += (pgs.sf60  or 0) * t
        sa_w  += (pgs.sa60  or 0) * t
        xgf_w += (pgs.xgf60 or 0) * t
        xga_w += (pgs.xga60 or 0) * t
        toi += t

        if pgs.median_shift_seconds is not None and t > 0:
            shift_seconds_list.append((pgs.median_shift_seconds, t))

        if pgs.icf:
            total_icf += pgs.icf
        if pgs.isf:
            total_isf += pgs.isf

        if pgs.personal_draws_taken:
            personal_taken += pgs.personal_draws_taken
        if pgs.personal_draws_won:
            personal_won += pgs.personal_draws_won
        if pgs.team_fo_wins_on_ice:
            fo_wins += pgs.team_fo_wins_on_ice
        if pgs.team_fo_losses_on_ice:
            fo_losses += pgs.team_fo_losses_on_ice

        trend.append(player_game_stats(pgs, g))

    # Weighted average of per-game median shift lengths (by TOI)
    if shift_seconds_list:
        total_weight = sum(w for _, w in shift_seconds_list)
        agg_shift = sum(s * w for s, w in shift_seconds_list) / total_weight if total_weight else None
    else:
        agg_shift = None

    # Season per-60 = weighted sum / total TOI; percentages derived from weighted sums
    def w60(w): return w / toi if toi > 0 else None

    xfsv_raw = safe_div(xga_w, fa_w)
    xfsv = (1 - xfsv_raw) if xfsv_raw is not None else None

    result = {
        "player_id": player.id,
        "player_name": player.name,
        "games_played": games_played,
        "small_sample": small_sample,
        "toi_5v5": toi if toi > 0 else None,
        "on_ice_cf_pct": pct(cf_w, ca_w),
        "on_ice_xgf_pct": pct(xgf_w, xga_w),
        "on_ice_sf_pct": pct(sf_w, sa_w),
        "cf60": w60(cf_w),
        "ca60": w60(ca_w),
        "ff60": w60(ff_w),
        "fa60": w60(fa_w),
        "sf60": w60(sf_w),
        "sa60": w60(sa_w),
        "xfsh_pct": safe_div(xgf_w, ff_w),
        "xfsv_pct": xfsv,
        "icf": total_icf if total_icf > 0 else None,
        "isf": total_isf if total_isf > 0 else None,
        "median_shift_seconds": agg_shift,
        "personal_fo_pct": safe_div(personal_won, personal_taken) if personal_taken > 0 else None,
        "on_ice_fo_pct": pct(fo_wins, fo_losses) if (fo_wins + fo_losses) > 0 else None,
        "trend": trend,
    }
    rows_by_game_id = {r.game_id: r for r in pgs_rows}
    result["availability"] = _availability_for(games, player_stat_keys, rows_by_game_id)
    return result


def top_flags(flags: list, n: int = 3) -> list:
    """Return top n flags sorted by |z_score| descending, None z_scores last."""
    def sort_key(f):
        z = getattr(f, "z_score", None)
        return (0 if z is None else 1, abs(z) if z is not None else 0)
    return sorted(flags, key=sort_key, reverse=True)[:n]
