"""Tier 3 stat computations — Shot Threat by Scenario, Defensive Disruption Index.

All functions are PURE — take pre-loaded rows, return dicts. See spec §9.9
and §9.11 for formulas.

Goalie stats (§9.10) are deferred to Phase 4b.
"""
from typing import Optional, Union


_LOCATIONS = [
    "slot", "center", "right_flank", "left_flank",
    "blue_line_right", "blue_line_center", "blue_line_left",
]
_TYPES = ["slapshot", "wristshot"]


def _pct(numer: int, denom: int) -> Optional[float]:
    return (numer / denom) if denom > 0 else None


def _per60(count: int, toi_minutes: Union[float, int]) -> Optional[float]:
    if toi_minutes <= 0 or count == 0:
        return None
    return count * 60.0 / toi_minutes


def shot_threat_by_scenario(shots_rows: list, pgs_rows: list) -> dict:
    """Aggregate a player's shots across strength / context / location / type (§9.11).

    Returns nested dict keyed by axis; each cell has shots/on_goal counts,
    on_goal_pct, and (for strength) shots_per_60 vs the corresponding TOI.

    Games with any PlayerGameShotsInStat data count; TOI is summed from
    PlayerGameStats rows (matching game_ids).

    Note: `games` counts rows in `shots_rows` that have at least one populated
    key stat (goals, shots, PP/SH shots). The caller is responsible for
    pre-filtering `shots_rows` and `pgs_rows` to the same game set for
    the same player.
    """
    total_shots = 0
    total_on_goal = 0
    total_goals = 0
    pp_shots = pp_on = 0
    sh_shots = sh_on = 0
    positional_shots = positional_on = 0
    counter_shots = counter_on = 0
    loc_shots = {loc: 0 for loc in _LOCATIONS}
    loc_on = {loc: 0 for loc in _LOCATIONS}
    type_shots = {t: 0 for t in _TYPES}
    type_on = {t: 0 for t in _TYPES}
    games = 0

    for r in shots_rows:
        has_data = any(
            getattr(r, k, None) not in (None, 0)
            for k in ("goals", "shots_total", "shots_on_goal",
                      "pp_shots_total", "sh_shots_total")
        )
        if has_data:
            games += 1
        total_goals += r.goals or 0
        total_shots += r.shots_total or 0
        total_on_goal += r.shots_on_goal or 0
        pp_shots += r.pp_shots_total or 0
        pp_on += r.pp_shots_on_goal or 0
        sh_shots += r.sh_shots_total or 0
        sh_on += r.sh_shots_on_goal or 0
        positional_shots += r.positional_shots_total or 0
        positional_on += r.positional_shots_on_goal or 0
        counter_shots += r.counter_shots_total or 0
        counter_on += r.counter_shots_on_goal or 0
        for loc in _LOCATIONS:
            loc_shots[loc] += getattr(r, f"{loc}_shots_total", None) or 0
            loc_on[loc] += getattr(r, f"{loc}_shots_on_goal", None) or 0
        for t in _TYPES:
            type_shots[t] += getattr(r, f"{t}_total", None) or 0
            type_on[t] += getattr(r, f"{t}_on_goal", None) or 0

    # 5v5 = total - pp - sh (assumption: total is all-strength)
    fv_shots = max(0, total_shots - pp_shots - sh_shots)
    fv_on = max(0, total_on_goal - pp_on - sh_on)

    toi_5v5 = sum((p.toi_5v5 or 0) for p in pgs_rows)
    toi_pp = sum((p.toi_pp or 0) for p in pgs_rows)
    toi_sh = sum((p.toi_sh or 0) for p in pgs_rows)

    return {
        "totals": {
            "goals": total_goals,
            "shots": total_shots,
            "shots_on_goal": total_on_goal,
            "toi_5v5_minutes": toi_5v5,
        },
        "by_strength": {
            "5v5": {"shots": fv_shots, "on_goal": fv_on,
                    "shots_per_60": _per60(fv_shots, toi_5v5),
                    "on_goal_pct": _pct(fv_on, fv_shots)},
            "pp": {"shots": pp_shots, "on_goal": pp_on,
                   "shots_per_60": _per60(pp_shots, toi_pp),
                   "on_goal_pct": _pct(pp_on, pp_shots)},
            "sh": {"shots": sh_shots, "on_goal": sh_on,
                   "shots_per_60": _per60(sh_shots, toi_sh),
                   "on_goal_pct": _pct(sh_on, sh_shots)},
        },
        "by_context": {
            "positional": {"shots": positional_shots, "on_goal": positional_on,
                           "on_goal_pct": _pct(positional_on, positional_shots)},
            "counter": {"shots": counter_shots, "on_goal": counter_on,
                        "on_goal_pct": _pct(counter_on, counter_shots)},
        },
        "by_location": {
            loc: {"shots": loc_shots[loc], "on_goal": loc_on[loc],
                  "on_goal_pct": _pct(loc_on[loc], loc_shots[loc])}
            for loc in _LOCATIONS
        },
        "by_type": {
            t: {"shots": type_shots[t], "on_goal": type_on[t],
                "on_goal_pct": _pct(type_on[t], type_shots[t])}
            for t in _TYPES
        },
        "games": games,
    }


def defensive_disruption_index(
    pgs_rows: list, instat_rows: list, shots_rows: list
) -> dict:
    """Composite off-puck defensive proxy (§9.9 with 2026-09-06 ruling).

    DDI/60 = (puck_recoveries + shots_blocked_defensively + DZ PB wins) × 60 ÷ TOI

    All three components require InStat. Returns ddi_per_60 = None when
    any component has NO data (no row provided a value) OR when total
    TOI is zero. Zero-value components with at least one populated row
    are treated as zero, not as missing data.
    """
    recoveries = 0
    blocks = 0
    dz_pb = 0
    recoveries_has_data = False
    blocks_has_data = False
    dz_pb_has_data = False
    games = 0
    total_toi = 0.0

    for r in instat_rows:
        if r.puck_recoveries is not None:
            recoveries += r.puck_recoveries
            recoveries_has_data = True
        if r.pb_won_dz is not None:
            dz_pb += r.pb_won_dz
            dz_pb_has_data = True
        if r.puck_recoveries is not None or r.pb_won_dz is not None:
            games += 1

    for r in shots_rows:
        if r.shots_blocked_defensively is not None:
            blocks += r.shots_blocked_defensively
            blocks_has_data = True

    for p in pgs_rows:
        total_toi += p.toi_5v5 or 0

    total_events = recoveries + blocks + dz_pb
    if total_toi <= 0 or not (recoveries_has_data and blocks_has_data and dz_pb_has_data):
        ddi_per_60 = None
    else:
        ddi_per_60 = total_events * 60.0 / total_toi

    return {
        "ddi_per_60": ddi_per_60,
        "components": {
            "puck_recoveries": recoveries,
            "shots_blocked_defensively": blocks,
            "dz_pb_wins": dz_pb,
        },
        "total_toi_minutes": total_toi,
        "games": games,
    }
