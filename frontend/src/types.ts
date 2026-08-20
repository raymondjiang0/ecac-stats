export interface Player {
  id: number
  name: string
  number: string | null
  position: string
  is_center: boolean
  active: boolean
}

export interface Game {
  id: number
  date: string
  opponent: string
  is_home: boolean
  season: string
  notes: string | null
  data_source: '49ing' | 'instat' | 'both'
}

export type GameCreate = Omit<Game, 'id' | 'data_source'>

export interface TeamGameStats {
  game_id: number
  // 5v5 core
  cf_for_5v5: number | null
  cf_against_5v5: number | null
  ff_for_5v5: number | null
  ff_against_5v5: number | null
  xgf_5v5: number | null
  xga_5v5: number | null
  // TOI decomposition (5v5 TOI is computed: total - pp - pk - other)
  total_game_time: number | null
  toi_pp: number | null
  toi_pk: number | null
  other_toi: number | null
  // 5v4 power play
  cf_for_5v4: number | null
  cf_against_5v4: number | null
  xgf_5v4: number | null
  xga_5v4: number | null
  // 4v5 penalty kill
  cf_for_4v5: number | null
  cf_against_4v5: number | null
  xgf_4v5: number | null
  xga_4v5: number | null
  // Attack scenario xGF (xG totals from Attack Scenarios tab, 5v5 filter)
  rush_xgf: number | null
  oz_fc_xgf: number | null
  oz_fo_xgf: number | null
  sust_pos_xgf: number | null
}

export interface PlayerGameStats {
  player_id: number
  game_id: number
  toi_5v5: number | null
  cf60: number | null
  ca60: number | null
  ff60: number | null
  fa60: number | null
  sf60: number | null
  sa60: number | null
  xgf60: number | null
  xga60: number | null
  icf: number | null
  isf: number | null
  median_shift_seconds: number | null
  personal_draws_taken: number | null
  personal_draws_won: number | null
  team_fo_wins_on_ice: number | null
  team_fo_losses_on_ice: number | null
}

export interface PlayerAggStats {
  player_id: number
  player_name: string
  games_played: number
  small_sample: boolean
  toi_5v5: number | null
  on_ice_cf_pct: number | null
  on_ice_xgf_pct: number | null
  on_ice_sf_pct: number | null
  cf60: number | null
  ca60: number | null
  ff60: number | null
  fa60: number | null
  sf60: number | null
  sa60: number | null
  xfsh_pct: number | null
  xfsv_pct: number | null
  icf: number | null
  isf: number | null
  median_shift_seconds: number | null
  personal_fo_pct: number | null
  on_ice_fo_pct: number | null
  trend: PlayerTrendPoint[]
  comparisons?: Record<string, StatComparison>
  flags?: PlayerFlag[]
  game_flags?: Record<number, PlayerFlag[]>
  availability?: Record<string, StatAvailability>
}

export interface PlayerTrendPoint {
  game_id: number
  date: string
  opponent: string
  toi_5v5: number | null
  on_ice_cf_pct: number | null
  on_ice_xgf_pct: number | null
  on_ice_sf_pct: number | null
  cf60: number | null
  ca60: number | null
  ff60: number | null
  fa60: number | null
  sf60: number | null
  sa60: number | null
  xfsh_pct: number | null
  xfsv_pct: number | null
  median_shift_seconds: number | null
  personal_fo_pct: number | null
  on_ice_fo_pct: number | null
}

export interface TeamAggStats {
  games_logged: number
  cf_pct: number | null
  xgf_pct: number | null
  xgf60: number | null
  xga60: number | null
  pp_cf_pct: number | null
  pp_xgf_pct: number | null
  pk_cf_pct: number | null
  pk_xgf_pct: number | null
  rush_share: number | null
  oz_fc_share: number | null
  oz_fo_share: number | null
  sust_pos_share: number | null
  cf_pct_trend: TrendPoint[]
  xgf_pct_trend: TrendPoint[]
  availability?: Record<string, StatAvailability>
}

export interface TrendPoint {
  game_id: number
  date: string
  opponent: string
  value: number | null
}

export interface StatAvailability {
  games: number
  sources: string[]
}

export interface Baseline {
  mean: number | null
  std: number | null
  n: number
}

export interface StatComparison {
  value: number | null
  cohort: string
  team_baseline: Baseline
  position_baseline: Baseline
  team_delta: number | null
  position_delta: number | null
  indicator: 'green' | 'yellow' | 'red' | 'neutral'
}

export interface PlayerFlag {
  kind: 'trend' | 'outlier'
  label: string
  direction: 'up' | 'down'
  z_score: number | null
  window_value: number | null
  baseline_value: number | null
  game_id: number | null
}
