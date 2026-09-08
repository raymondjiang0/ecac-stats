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
  contested_puck?: ContestedPuckStats
  zone_entry?: ZoneEntryStats
  turnover_ratio?: TurnoverRatioStats
  danger_share?: DangerShareStats
  impact_score?: ImpactScoreStats
  shot_threat?: ShotThreatStats
  ddi?: DDIStats
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
  special_teams_v2?: SpecialTeamsV2Stats
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

export interface IngestTeamStats {
  pp_shots: number | null
  pp_time_seconds_in_oz: number | null
  pp_time_seconds_total: number | null
  pk_opp_breakouts: number | null
  pp_opp_breakouts_allowed: number | null
  puck_possession_seconds_total: number | null
  oz_possession_seconds: number | null
  oz_possession_pct: number | null
  scoring_chance_shots: number | null
  scoring_chance_shots_on_goal: number | null
}

export interface IngestPlayerRow {
  jersey_number: string
  player_name: string
  [key: string]: string | number | null
}

export interface IngestMatrixRow {
  from_jersey: string
  from_name: string
  to_jersey: string
  to_name: string
  delivered?: number
  received?: number
  count?: number
}

export interface IngestPreview {
  instat_team_stats: IngestTeamStats
  instat_players_main: IngestPlayerRow[]
  instat_time_distribution: IngestPlayerRow[]
  instat_challenges: IngestPlayerRow[]
  instat_hit_matrix: IngestMatrixRow[]
  instat_pass_matrix: IngestMatrixRow[]
}

export interface IngestRun {
  id: number
  game_id: number
  filename: string
  uploaded_at: string
  status: 'pending_review' | 'committed' | 'discarded' | 'failed'
  parsed_json: { templates: IngestPreview; warnings: string[] }
  committed_at: string | null
  error: string | null
}

export interface ContestedPuckStats {
  overall_pct: number | null
  dz_pct: number | null
  oz_pct: number | null
  nz_pct: number | null
  games: number
}

export interface ZoneEntryStats {
  pass_pct: number | null
  stick_pct: number | null
  dump_pct: number | null
  total_entries: number
  games: number
}

export interface TurnoverRatioStats {
  dz_loss_share: number | null
  oz_recovery_share: number | null
  total_losses: number
  total_recoveries: number
  games: number
}

export interface DangerShareStats {
  share_pct: number | null
  shots_per_60: number | null
  player_sca_shots: number
  team_sca_shots: number
  games: number
}

export interface ImpactScoreComponent {
  z_xg?: number
  z_terr?: number
  z_battle?: number
  z_entry?: number
}

export interface ImpactScorePerGame {
  game_id: number
  impact: number | null
  components: ImpactScoreComponent
  toi_5v5: number
}

export interface ImpactScoreStats {
  score: number | null
  games: number
  components_used: string[]
  clamped: boolean
  per_game: ImpactScorePerGame[]
}

export interface SpecialTeamsV2Stats {
  pp_shots_per_min: number | null
  pp_oz_ratio: number | null
  pk_opp_breakout_rate: number | null
  pp_minutes: number | null
  pk_count: number
  games: number
}

export interface ScenarioCell {
  shots: number
  on_goal: number
  shots_per_60?: number | null   // only on strength cells
  on_goal_pct: number | null
}

export interface ShotThreatStats {
  totals: {
    goals: number
    shots: number
    shots_on_goal: number
    toi_5v5_minutes: number
  }
  by_strength: {
    '5v5': ScenarioCell
    pp: ScenarioCell
    sh: ScenarioCell
  }
  by_context: {
    positional: ScenarioCell
    counter: ScenarioCell
  }
  by_location: {
    slot: ScenarioCell
    center: ScenarioCell
    right_flank: ScenarioCell
    left_flank: ScenarioCell
    blue_line_right: ScenarioCell
    blue_line_center: ScenarioCell
    blue_line_left: ScenarioCell
  }
  by_type: {
    slapshot: ScenarioCell
    wristshot: ScenarioCell
  }
  games: number
}

export interface DDIComponents {
  puck_recoveries: number
  shots_blocked_defensively: number
  dz_pb_wins: number
}

export interface DDIStats {
  ddi_per_60: number | null
  components: DDIComponents
  total_toi_minutes: number
  games: number
}
