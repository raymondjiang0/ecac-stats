from pydantic import BaseModel, field_validator
from typing import Optional
from datetime import date


# ── Players ──────────────────────────────────────────────────────────────────

class PlayerCreate(BaseModel):
    name: str
    number: Optional[str] = None
    position: str
    is_center: bool = False
    active: bool = True


class PlayerUpdate(BaseModel):
    name: Optional[str] = None
    number: Optional[str] = None
    position: Optional[str] = None
    is_center: Optional[bool] = None
    active: Optional[bool] = None


class PlayerOut(BaseModel):
    id: int
    name: str
    number: Optional[str]
    position: str
    is_center: bool
    active: bool

    model_config = {"from_attributes": True}


# ── Games ─────────────────────────────────────────────────────────────────────

class GameCreate(BaseModel):
    date: date
    opponent: str
    is_home: bool
    season: str = "2025-26"
    notes: Optional[str] = None


class GameUpdate(BaseModel):
    date: Optional[date] = None
    opponent: Optional[str] = None
    is_home: Optional[bool] = None
    season: Optional[str] = None
    notes: Optional[str] = None


class GameOut(BaseModel):
    id: int
    date: date
    opponent: str
    is_home: bool
    season: str
    notes: Optional[str]

    model_config = {"from_attributes": True}


# ── Team Game Stats ───────────────────────────────────────────────────────────

class TeamGameStatsCreate(BaseModel):
    # 5v5 core
    cf_for_5v5: Optional[float] = None
    cf_against_5v5: Optional[float] = None
    ff_for_5v5: Optional[float] = None
    ff_against_5v5: Optional[float] = None
    xgf_5v5: Optional[float] = None
    xga_5v5: Optional[float] = None

    # TOI decomposition (5v5 TOI is computed, not entered directly)
    total_game_time: Optional[float] = 60
    toi_pp: Optional[float] = None
    toi_pk: Optional[float] = None
    other_toi: Optional[float] = 0

    # 5v4 power play
    cf_for_5v4: Optional[float] = None
    cf_against_5v4: Optional[float] = None
    xgf_5v4: Optional[float] = None
    xga_5v4: Optional[float] = None

    # 4v5 penalty kill
    cf_for_4v5: Optional[float] = None
    cf_against_4v5: Optional[float] = None
    xgf_4v5: Optional[float] = None
    xga_4v5: Optional[float] = None

    # Attack scenario xGF (from 49ing Attack Scenarios tab, 5v5 filter — xG only, no counts)
    rush_xgf: Optional[float] = None
    oz_fc_xgf: Optional[float] = None
    oz_fo_xgf: Optional[float] = None
    sust_pos_xgf: Optional[float] = None


class TeamGameStatsOut(TeamGameStatsCreate):
    game_id: int

    model_config = {"from_attributes": True}


# ── Player Game Stats ─────────────────────────────────────────────────────────

class PlayerGameStatsCreate(BaseModel):
    toi_5v5: Optional[float] = None
    cf60: Optional[float] = None
    ca60: Optional[float] = None
    ff60: Optional[float] = None
    fa60: Optional[float] = None
    sf60: Optional[float] = None
    sa60: Optional[float] = None
    xgf60: Optional[float] = None
    xga60: Optional[float] = None
    icf: Optional[float] = None
    isf: Optional[float] = None
    median_shift_seconds: Optional[float] = None
    personal_draws_taken: Optional[float] = None
    personal_draws_won: Optional[float] = None
    team_fo_wins_on_ice: Optional[float] = None
    team_fo_losses_on_ice: Optional[float] = None


class PlayerGameStatsOut(PlayerGameStatsCreate):
    player_id: int
    game_id: int

    model_config = {"from_attributes": True}


# ── Computed Stats ────────────────────────────────────────────────────────────

class TeamAggStats(BaseModel):
    games_logged: int
    cf_pct: Optional[float]
    xgf_pct: Optional[float]
    xgf60: Optional[float]
    xga60: Optional[float]
    pp_cf_pct: Optional[float]
    pp_xgf_pct: Optional[float]
    pk_cf_pct: Optional[float]
    pk_xgf_pct: Optional[float]
    rush_share: Optional[float]
    oz_fc_share: Optional[float]
    oz_fo_share: Optional[float]
    sust_pos_share: Optional[float]
    # Per-game trend for CF% and xGF%
    cf_pct_trend: list
    xgf_pct_trend: list


class PlayerTrendPoint(BaseModel):
    game_id: int
    date: date
    opponent: str
    on_ice_cf_pct: Optional[float]
    on_ice_xgf_pct: Optional[float]
    on_ice_sf_pct: Optional[float]
    cf60: Optional[float]
    ca60: Optional[float]
    ff60: Optional[float]
    fa60: Optional[float]
    sf60: Optional[float]
    sa60: Optional[float]
    xfsh_pct: Optional[float]
    xfsv_pct: Optional[float]
    median_shift_seconds: Optional[float]
    personal_fo_pct: Optional[float]
    on_ice_fo_pct: Optional[float]
    toi_5v5: Optional[float]


class PlayerAggStats(BaseModel):
    player_id: int
    player_name: str
    games_played: int
    small_sample: bool
    toi_5v5: Optional[float]
    on_ice_cf_pct: Optional[float]
    on_ice_xgf_pct: Optional[float]
    on_ice_sf_pct: Optional[float]
    cf60: Optional[float]
    ca60: Optional[float]
    ff60: Optional[float]
    fa60: Optional[float]
    sf60: Optional[float]
    sa60: Optional[float]
    xfsh_pct: Optional[float]
    xfsv_pct: Optional[float]
    icf: Optional[float]
    isf: Optional[float]
    median_shift_seconds: Optional[float]
    personal_fo_pct: Optional[float]
    on_ice_fo_pct: Optional[float]
    trend: list[PlayerTrendPoint]
