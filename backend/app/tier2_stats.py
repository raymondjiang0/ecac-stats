"""Tier 2 stat computations — Contested Puck Win %, Zone Entry Composition,
Turnover Location Ratio, Special Teams v2, Danger-Zone Shot Share, Impact Score.

All functions in this module are PURE — they take already-loaded SQLAlchemy
rows and return dicts. Callers (typically the enrichment layer) load the rows
via the helpers in enrichment.py and pass them in.

See spec §9.1–§9.6 for formulas.
"""
from typing import Optional


def contested_puck_win_pct(instat_rows: list) -> dict:
    """Aggregate puck-battle W% overall and by zone (§9.2).

    Percentages in [0, 1]. Zones with zero total attempts across the window
    return None. `games` counts rows with any pb_total_* > 0.
    """
    won_dz = tot_dz = won_oz = tot_oz = won_nz = tot_nz = 0
    games = 0
    for r in instat_rows:
        has_any = False
        if r.pb_total_dz and r.pb_total_dz > 0:
            won_dz += r.pb_won_dz or 0
            tot_dz += r.pb_total_dz
            has_any = True
        if r.pb_total_oz and r.pb_total_oz > 0:
            won_oz += r.pb_won_oz or 0
            tot_oz += r.pb_total_oz
            has_any = True
        if r.pb_total_nz and r.pb_total_nz > 0:
            won_nz += r.pb_won_nz or 0
            tot_nz += r.pb_total_nz
            has_any = True
        if has_any:
            games += 1

    def _pct(w: int, t: int) -> Optional[float]:
        return w / t if t > 0 else None

    total_won = won_dz + won_oz + won_nz
    total_tot = tot_dz + tot_oz + tot_nz
    return {
        "overall_pct": _pct(total_won, total_tot),
        "dz_pct": _pct(won_dz, tot_dz),
        "oz_pct": _pct(won_oz, tot_oz),
        "nz_pct": _pct(won_nz, tot_nz),
        "games": games,
    }


def zone_entry_composition(instat_rows: list) -> dict:
    """Aggregate entry method percentages (§9.4).

    Returns pass/stick/dump percentages as fractions in [0, 1] summing to 1.0
    (when total > 0). All-None when the window has no entries.
    """
    pass_total = stick_total = dump_total = 0
    games = 0
    for r in instat_rows:
        p = r.entries_pass or 0
        s = r.entries_stick or 0
        d = r.entries_dump or 0
        if (p + s + d) > 0:
            pass_total += p
            stick_total += s
            dump_total += d
            games += 1

    total = pass_total + stick_total + dump_total
    if total == 0:
        return {
            "pass_pct": None, "stick_pct": None, "dump_pct": None,
            "total_entries": 0, "games": 0,
        }
    return {
        "pass_pct": pass_total / total,
        "stick_pct": stick_total / total,
        "dump_pct": dump_total / total,
        "total_entries": total,
        "games": games,
    }


def turnover_location_ratio(instat_rows: list) -> dict:
    """Aggregate turnover-location metrics (§9.5).

    - dz_loss_share: DZ losses ÷ total losses
    - oz_recovery_share: OZ recoveries ÷ total recoveries
    Both are None when their denominator is 0.
    """
    total_losses = 0
    dz_losses = 0
    total_recoveries = 0
    oz_recoveries = 0
    games = 0
    for r in instat_rows:
        losses = r.puck_losses or 0
        recoveries = r.puck_recoveries or 0
        if losses > 0 or recoveries > 0:
            games += 1
        total_losses += losses
        dz_losses += r.puck_losses_dz or 0
        total_recoveries += recoveries
        oz_recoveries += r.puck_recoveries_oz or 0

    return {
        "dz_loss_share": (dz_losses / total_losses) if total_losses > 0 else None,
        "oz_recovery_share": (oz_recoveries / total_recoveries) if total_recoveries > 0 else None,
        "total_losses": total_losses,
        "total_recoveries": total_recoveries,
        "games": games,
    }


def special_teams_v2(team_instat_rows: list) -> dict:
    """Team-level advanced special-teams stats (§9.3).

    - pp_shots_per_min: total PP shots ÷ total PP minutes
    - pp_oz_ratio: PP OZ seconds ÷ total PP seconds
    - pk_opp_breakout_rate: total opp breakouts allowed on PK ÷ games with PK data
    """
    total_pp_shots = 0
    total_pp_seconds = 0
    total_oz_pp_seconds = 0
    total_pk_breakouts = 0
    pk_count = 0
    games = 0

    for r in team_instat_rows:
        pp_secs = r.pp_time_seconds_total or 0
        oz_secs = r.pp_time_seconds_in_oz or 0
        pp_shots = r.pp_shots or 0
        pk_bk = r.pk_opp_breakouts

        has_data = pp_secs > 0 or pp_shots > 0 or pk_bk is not None
        if has_data:
            games += 1
        if pp_secs > 0:
            total_pp_seconds += pp_secs
            total_oz_pp_seconds += oz_secs
            total_pp_shots += pp_shots
        if pk_bk is not None:
            total_pk_breakouts += pk_bk
            pk_count += 1

    pp_minutes = total_pp_seconds / 60.0 if total_pp_seconds > 0 else (
        0.0 if any(r.pp_time_seconds_total is not None for r in team_instat_rows) else None
    )

    return {
        "pp_shots_per_min": (total_pp_shots / pp_minutes) if pp_minutes and pp_minutes > 0 else None,
        "pp_oz_ratio": (total_oz_pp_seconds / total_pp_seconds) if total_pp_seconds > 0 else None,
        "pk_opp_breakout_rate": (total_pk_breakouts / pk_count) if pk_count > 0 else None,
        "pp_minutes": pp_minutes,
        "pk_count": pk_count,
        "games": games,
    }


def danger_zone_shot_share(
    instat_rows: list,
    team_instat_rows: list,
    pgs_rows: list,
) -> dict:
    """Player's share of team's high-danger shots + per-60 rate (§9.6).

    Numerator: sum of player's SCA shots (or `shots` as a proxy until Phase 4
    adds true per-player scoring-chance shot tracking).
    Denominator: sum of team's scoring_chance_shots across the same games.
    """
    player_sca = 0
    games_with_data = 0
    for r in instat_rows:
        sca = getattr(r, "scoring_chance_shots", None)
        val = sca if sca is not None else (r.shots or 0)
        if val > 0:
            games_with_data += 1
        player_sca += val

    team_sca = sum((t.scoring_chance_shots or 0) for t in team_instat_rows)
    total_toi = sum((p.toi_5v5 or 0) for p in pgs_rows)

    return {
        "share_pct": (player_sca / team_sca) if team_sca > 0 else None,
        "shots_per_60": (player_sca * 60.0 / total_toi) if total_toi > 0 else None,
        "player_sca_shots": player_sca,
        "team_sca_shots": team_sca,
        "games": games_with_data,
    }
