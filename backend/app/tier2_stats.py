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
