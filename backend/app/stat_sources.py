"""Source-availability declarations for every tracked stat.

Each stat_key maps to the set of Game.data_source values that supply the
data required to compute it. A game with data_source == "both" satisfies
either single-source requirement (source merge preference is 49ing per
spec §2, applied at the aggregation layer per-stat).

Adding a new stat: add its key here with the sources it needs, or the
aggregation layer will silently drop all games from its window.
"""
from typing import Iterable
from .models import Game


# Sources for stats produced by aggregate_player_stats
_PLAYER_STAT_SOURCES: dict[str, set[str]] = {
    # 49ing supplies per-60 rates and on-ice percentages directly.
    # InStat supplies raw Corsi counts that can be scaled to per-60.
    # Both are marked here; aggregation prefers 49ing when a game has both.
    "toi_5v5":         {"49ing", "instat"},
    "on_ice_cf_pct":   {"49ing", "instat"},
    "on_ice_xgf_pct":  {"49ing"},               # xG not available from InStat per player
    "on_ice_sf_pct":   {"49ing", "instat"},
    "cf60":            {"49ing", "instat"},
    "ca60":            {"49ing", "instat"},
    "ff60":            {"49ing"},
    "fa60":            {"49ing"},
    "sf60":            {"49ing", "instat"},
    "sa60":            {"49ing", "instat"},
    "xfsh_pct":        {"49ing"},
    "xfsv_pct":        {"49ing"},
    "icf":             {"49ing", "instat"},     # ICF = shots attempted (either source has raw counts)
    "isf":             {"49ing", "instat"},
    "median_shift_seconds": {"49ing"},          # 49ing exposes median directly; InStat exposes shift timeline only
    "personal_fo_pct": {"49ing", "instat"},
    "on_ice_fo_pct":   {"49ing", "instat"},
}

# Sources for stats produced by aggregate_team_stats
_TEAM_STAT_SOURCES: dict[str, set[str]] = {
    "cf_pct":         {"49ing", "instat"},
    "xgf_pct":        {"49ing"},                # team xG per game — 49ing only
    "xgf60":          {"49ing"},
    "xga60":          {"49ing"},
    "pp_cf_pct":      {"49ing", "instat"},
    "pp_xgf_pct":     {"49ing"},
    "pk_cf_pct":      {"49ing", "instat"},
    "pk_xgf_pct":     {"49ing"},
    "rush_share":     {"49ing"},                # attack-scenario xG — 49ing only per spec §9
    "oz_fc_share":    {"49ing"},
    "oz_fo_share":    {"49ing"},
    "sust_pos_share": {"49ing"},
}

STAT_SOURCES: dict[str, set[str]] = {
    **_PLAYER_STAT_SOURCES,
    **_TEAM_STAT_SOURCES,
}

# Phase-2/3 stats declared here even though no aggregation yet reads them,
# so the availability layer answers correctly the moment they land:
STAT_SOURCES["puck_battle_pct"] = {"instat"}
STAT_SOURCES["pb_dz_pct"] = {"instat"}
STAT_SOURCES["pb_oz_pct"] = {"instat"}
STAT_SOURCES["pb_nz_pct"] = {"instat"}
STAT_SOURCES["entry_pass_pct"] = {"instat"}
STAT_SOURCES["entry_stick_pct"] = {"instat"}
STAT_SOURCES["entry_dump_pct"] = {"instat"}
STAT_SOURCES["impact_score"] = {"49ing", "instat"}


def stat_available_from(data_source: str, stat_key: str) -> bool:
    """Does a game tagged with data_source supply the data needed for stat_key?"""
    needed = STAT_SOURCES.get(stat_key)
    if needed is None:
        return False
    if data_source == "both":
        # Any-of; both sides are present so anything either source has is available.
        return bool(needed)
    return data_source in needed


def games_with_stat(games: Iterable[Game], stat_key: str) -> list[Game]:
    """Filter to games where this stat's source data is available."""
    return [g for g in games if stat_available_from(g.data_source, stat_key)]
