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
