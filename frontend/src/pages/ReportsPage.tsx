import { useState, useEffect, useCallback } from 'react'
import { getPlayers, getAllPlayerAggStats, getGames, downloadPlayerReport, downloadTeamReport, exportAllData, getPlayerAggStats, getTeamAggStats } from '../api/client'
import type { Player, PlayerAggStats, TeamAggStats, Game } from '../types'
import SmallSampleBadge from '../components/SmallSampleBadge'
import FlagPanel from '../components/FlagPanel'
import ComparisonRow from '../components/ComparisonRow'
import GameFlagBadge from '../components/GameFlagBadge'
import StatCard from '../components/StatCard'
import PuckBattleBlock from '../components/PuckBattleBlock'
import EntryCompositionBar from '../components/EntryCompositionBar'
import ImpactScoreCard from '../components/ImpactScoreCard'

function fmt(v: number | null, mult = 100, dec = 1): string {
  if (v === null || v === undefined) return '—'
  return (v * mult).toFixed(dec) + (mult === 100 ? '%' : '')
}
function fmtRaw(v: number | null, dec = 2): string {
  if (v === null || v === undefined) return '—'
  return v.toFixed(dec)
}

// Preset options — "last N games" computed from sorted game dates
type Preset = 'all' | 'last1' | 'last3' | 'last5' | 'last10' | 'custom'

const PRESETS: { key: Preset; label: string }[] = [
  { key: 'all',    label: 'All Time' },
  { key: 'last1',  label: 'Last Game' },
  { key: 'last3',  label: 'Last 3' },
  { key: 'last5',  label: 'Last 5' },
  { key: 'last10', label: 'Last 10' },
  { key: 'custom', label: 'Custom Dates' },
]

function computeDateRange(preset: Preset, games: Game[], customFrom: string, customTo: string): { from?: string; to?: string } {
  if (preset === 'all') return {}
  if (preset === 'custom') return { from: customFrom || undefined, to: customTo || undefined }
  const sorted = [...games].sort((a, b) => a.date.localeCompare(b.date))
  const n = { last1: 1, last3: 3, last5: 5, last10: 10 }[preset] ?? 5
  const recent = sorted.slice(-n)
  if (recent.length === 0) return {}
  return { from: recent[0].date, to: recent[recent.length - 1].date }
}

function gamesInRange(games: Game[], from?: string, to?: string): Game[] {
  return games.filter(g => {
    if (from && g.date < from) return false
    if (to && g.date > to) return false
    return true
  })
}

export default function ReportsPage() {
  const [players, setPlayers] = useState<Player[]>([])
  const [games, setGames] = useState<Game[]>([])
  const [aggStats, setAggStats] = useState<Record<number, PlayerAggStats>>({})
  const [loading, setLoading] = useState(true)
  const [statsLoading, setStatsLoading] = useState(false)
  const [downloading, setDownloading] = useState<number | 'team' | null>(null)
  const [exporting, setExporting] = useState(false)
  const [expandedPlayerId, setExpandedPlayerId] = useState<number | null>(null)
  const [detailAggs, setDetailAggs] = useState<Record<number, PlayerAggStats>>({})
  const [teamAgg, setTeamAgg] = useState<TeamAggStats | null>(null)

  // Filter state
  const [preset, setPreset] = useState<Preset>('all')
  const [customFrom, setCustomFrom] = useState('')
  const [customTo, setCustomTo] = useState('')

  const { from: dateFrom, to: dateTo } = computeDateRange(preset, games, customFrom, customTo)
  const visibleGames = gamesInRange(games, dateFrom, dateTo)

  useEffect(() => {
    Promise.all([getPlayers(), getGames()]).then(([ps, gs]) => {
      setPlayers(ps.filter(p => p.active))
      setGames(gs)
    }).finally(() => setLoading(false))
  }, [])

  const refreshStats = useCallback(() => {
    setStatsLoading(true)
    Promise.all([
      getAllPlayerAggStats(dateFrom, dateTo),
      getTeamAggStats(dateFrom, dateTo),
    ]).then(([aggs, tAgg]) => {
      const map: Record<number, PlayerAggStats> = {}
      aggs.forEach(a => { map[a.player_id] = a })
      setAggStats(map)
      setTeamAgg(tAgg)
    }).finally(() => setStatsLoading(false))
  }, [dateFrom, dateTo])

  useEffect(() => {
    if (!loading) refreshStats()
  }, [loading, dateFrom, dateTo])

  useEffect(() => {
    setDetailAggs({})
    setExpandedPlayerId(null)
  }, [dateFrom, dateTo])

  async function downloadPlayer(p: Player) {
    setDownloading(p.id)
    try { await downloadPlayerReport(p.id, p.name, dateFrom, dateTo) }
    catch { alert('PDF generation failed — is the backend running?') }
    finally { setDownloading(null) }
  }

  async function downloadTeam() {
    setDownloading('team')
    try { await downloadTeamReport(dateFrom, dateTo) }
    catch { alert('PDF generation failed — is the backend running?') }
    finally { setDownloading(null) }
  }

  async function toggleExpand(playerId: number) {
    if (expandedPlayerId === playerId) {
      setExpandedPlayerId(null)
      return
    }
    setExpandedPlayerId(playerId)
    if (!detailAggs[playerId]) {
      try {
        const agg = await getPlayerAggStats(playerId, dateFrom, dateTo)
        setDetailAggs(prev => ({ ...prev, [playerId]: agg }))
      } catch {
        // detail fetch failed silently — panel will render without data
      }
    }
  }

  if (loading) return <div className="loading">Loading…</div>

  const rangeLabel = (() => {
    if (!dateFrom && !dateTo) return 'Full season'
    if (dateFrom && dateTo) return `${dateFrom} → ${dateTo}`
    if (dateFrom) return `From ${dateFrom}`
    return `Through ${dateTo}`
  })()

  return (
    <>
      <div className="page-header">
        <div>
          <div className="page-title">Reports</div>
          <div className="page-subtitle">Generate PDFs for staff meetings</div>
        </div>
        <button
          className="btn btn-ghost"
          onClick={async () => { setExporting(true); try { await exportAllData() } catch { alert('Export failed') } finally { setExporting(false) } }}
          disabled={exporting}
        >
          {exporting ? 'Exporting…' : '↓ JSON Backup'}
        </button>
      </div>

      {/* ── Date range filter ── */}
      <div className="card" style={{ marginBottom: 24, padding: '16px 20px' }}>
        <div style={{ fontSize: 10, fontWeight: 700, letterSpacing: '0.12em', textTransform: 'uppercase', color: 'var(--text-secondary)', marginBottom: 12 }}>
          Date Range — Reports &amp; Stat Previews
        </div>

        {/* Preset buttons */}
        <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', marginBottom: 14 }}>
          {PRESETS.map(p => (
            <button
              key={p.key}
              onClick={() => setPreset(p.key)}
              style={{
                padding: '6px 14px',
                borderRadius: 6,
                fontSize: 12,
                fontWeight: 600,
                border: `1px solid ${preset === p.key ? 'var(--crimson)' : 'var(--border)'}`,
                background: preset === p.key ? 'var(--crimson-dim)' : 'transparent',
                color: preset === p.key ? 'var(--crimson)' : 'var(--text-secondary)',
                cursor: 'pointer',
                transition: 'all 0.15s',
              }}
            >
              {p.label}
            </button>
          ))}
        </div>

        {/* Custom date inputs */}
        {preset === 'custom' && (
          <div style={{ display: 'flex', gap: 12, alignItems: 'center', marginBottom: 14 }}>
            <div className="form-field" style={{ flex: 1 }}>
              <label>From</label>
              <input type="date" value={customFrom} onChange={e => setCustomFrom(e.target.value)} />
            </div>
            <div style={{ color: 'var(--text-secondary)', paddingTop: 20 }}>→</div>
            <div className="form-field" style={{ flex: 1 }}>
              <label>To</label>
              <input type="date" value={customTo} onChange={e => setCustomTo(e.target.value)} />
            </div>
          </div>
        )}

        {/* Range summary */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 16 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <span style={{
              fontSize: 26,
              fontWeight: 700,
              color: visibleGames.length > 0 ? 'var(--ice)' : 'var(--text-secondary)',
              lineHeight: 1,
            }}>
              {visibleGames.length}
            </span>
            <span style={{ fontSize: 12, color: 'var(--text-secondary)' }}>
              game{visibleGames.length !== 1 ? 's' : ''} in range
            </span>
          </div>
          <div style={{ fontSize: 12, color: 'var(--text-secondary)', borderLeft: '1px solid var(--border)', paddingLeft: 16 }}>
            {rangeLabel}
          </div>
          {visibleGames.length > 0 && (
            <div style={{ fontSize: 11, color: 'var(--text-secondary)' }}>
              {visibleGames.map(g => g.opponent).join(' · ')}
            </div>
          )}
        </div>
      </div>

      {visibleGames.length === 0 && (preset !== 'all') && (
        <div className="alert alert-error" style={{ marginBottom: 20 }}>
          No games found in this date range. Adjust the filter or log games first.
        </div>
      )}

      {/* Team report */}
      <div className="section-divider">Team Report</div>
      <div className="card" style={{ marginBottom: 24, display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <div>
          <div style={{ fontWeight: 700, fontSize: 15 }}>Harvard ECAC — {rangeLabel}</div>
          <div style={{ fontSize: 12, color: 'var(--text-secondary)', marginTop: 4 }}>
            6 team stats · {visibleGames.length} game{visibleGames.length !== 1 ? 's' : ''}
          </div>
        </div>
        <button
          className="btn btn-primary"
          onClick={downloadTeam}
          disabled={downloading === 'team' || visibleGames.length === 0}
          style={{ flexShrink: 0 }}
        >
          {downloading === 'team' ? 'Generating…' : 'Download Team PDF'}
        </button>
      </div>

      {teamAgg && teamAgg.special_teams_v2 && teamAgg.special_teams_v2.games > 0 && (
        <div className="card" style={{ marginBottom: 24 }}>
          <h3 style={{ fontSize: 14, marginBottom: 12, color: 'var(--text-secondary)' }}>
            Special Teams (Advanced)
          </h3>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 8 }}>
            <StatCard
              label="PP Shots/min"
              primary={teamAgg.special_teams_v2.pp_shots_per_min === null ? '—' : teamAgg.special_teams_v2.pp_shots_per_min.toFixed(2)}
            />
            <StatCard
              label="PP OZ Ratio"
              primary={teamAgg.special_teams_v2.pp_oz_ratio === null ? '—' : `${(teamAgg.special_teams_v2.pp_oz_ratio * 100).toFixed(1)}%`}
            />
            <StatCard
              label="PK Opp-Breakout Rate"
              primary={teamAgg.special_teams_v2.pk_opp_breakout_rate === null ? '—' : teamAgg.special_teams_v2.pk_opp_breakout_rate.toFixed(2)}
            />
          </div>
        </div>
      )}

      {/* Player reports */}
      <div className="section-divider">Player Reports</div>
      {players.length === 0 && (
        <div className="empty-state">
          <div className="empty-state-title">No active players</div>
          <div className="empty-state-body">Add players to the roster first.</div>
        </div>
      )}

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 14 }}>
        {players.map(p => {
          const agg = aggStats[p.id]
          return (
            <div key={p.id} className="card" style={{ borderTop: '3px solid var(--crimson)', opacity: statsLoading ? 0.6 : 1, transition: 'opacity 0.2s' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 12 }}>
                <div>
                  <div style={{ fontWeight: 700, fontSize: 15 }}>{p.name}</div>
                  <div style={{ fontSize: 11, color: 'var(--text-secondary)', marginTop: 3 }}>
                    {p.number ? `#${p.number} · ` : ''}{p.position}{p.is_center ? ' (C)' : ''}
                  </div>
                </div>
                <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-end', gap: 4 }}>
                  {agg && (
                    <span style={{ fontSize: 11, fontWeight: 600, color: agg.games_played > 0 ? 'var(--ice)' : 'var(--text-secondary)' }}>
                      {agg.games_played} game{agg.games_played !== 1 ? 's' : ''}
                    </span>
                  )}
                  {agg?.small_sample && <SmallSampleBadge n={agg.games_played} />}
                </div>
              </div>

              {agg && agg.games_played > 0 ? (
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 6, marginBottom: 14 }}>
                  {[
                    ['On-Ice CF%',   fmt(agg.on_ice_cf_pct)],
                    ['On-Ice xGF%',  fmt(agg.on_ice_xgf_pct)],
                    ['On-Ice SF%',   fmt(agg.on_ice_sf_pct)],
                    ['CF60',         fmtRaw(agg.cf60, 1)],
                    ['SF60',         fmtRaw(agg.sf60, 1)],
                    ['TOI (min)',     fmtRaw(agg.toi_5v5, 1)],
                  ].map(([label, val]) => (
                    <div key={label} style={{ padding: '6px 10px', background: 'var(--surface)', borderRadius: 6 }}>
                      <div style={{ fontSize: 9, fontWeight: 700, letterSpacing: '0.08em', textTransform: 'uppercase', color: 'var(--text-secondary)', marginBottom: 2 }}>{label}</div>
                      <div style={{ fontSize: 14, fontWeight: 700, color: 'var(--text)' }}>{val}</div>
                    </div>
                  ))}
                </div>
              ) : (
                <div style={{ fontSize: 12, color: 'var(--text-secondary)', marginBottom: 14, fontStyle: 'italic' }}>
                  No data in this range
                </div>
              )}

              <div style={{ display: 'flex', gap: 8 }}>
                <button
                  className="btn btn-primary"
                  onClick={() => downloadPlayer(p)}
                  disabled={downloading === p.id || visibleGames.length === 0}
                  style={{ flex: 1 }}
                >
                  {downloading === p.id ? 'Generating PDF…' : 'Download Player PDF'}
                </button>
                <button
                  className="btn btn-ghost"
                  onClick={() => toggleExpand(p.id)}
                  style={{ flexShrink: 0, padding: '0 14px' }}
                  title={expandedPlayerId === p.id ? 'Collapse detail' : 'Expand detail'}
                >
                  {expandedPlayerId === p.id ? '▲' : '▼'}
                </button>
              </div>

              {expandedPlayerId === p.id && (
                <div style={{ marginTop: 12, padding: '16px 0 0 0' }}>
                  {detailAggs[p.id] ? (
                    <>
                      <FlagPanel flags={detailAggs[p.id].flags ?? []} />
                      <div>
                        {detailAggs[p.id].comparisons && Object.entries({
                          toi_5v5:         { label: 'TOI',           unit: 'min'   as const },
                          cf60:            { label: 'CF60',          unit: 'per60' as const },
                          ca60:            { label: 'CA60',          unit: 'per60' as const },
                          on_ice_xgf_pct:  { label: 'xGF%',         unit: 'pct'   as const },
                          xfsh_pct:        { label: 'xFSh%',        unit: 'pct'   as const },
                          personal_fo_pct: { label: 'Personal FO%', unit: 'pct'   as const },
                        }).map(([key, meta]) => {
                          const cmp = detailAggs[p.id].comparisons?.[key]
                          if (!cmp) return null
                          return <ComparisonRow key={key} label={meta.label} comparison={cmp} unit={meta.unit} />
                        })}
                      </div>
                      {(() => {
                        const agg = detailAggs[p.id]
                        return (
                          <>
                            {agg.impact_score && agg.impact_score.games > 0 && (
                              <ImpactScoreCard data={agg.impact_score} />
                            )}
                            <PuckBattleBlock data={agg.contested_puck} />
                            <EntryCompositionBar data={agg.zone_entry} />

                            {agg.turnover_ratio && agg.turnover_ratio.games > 0 && (
                              <div style={{ marginTop: 16 }}>
                                <h3 style={{ fontSize: 14, marginBottom: 8, color: 'var(--text-secondary)' }}>
                                  Turnover Location
                                </h3>
                                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: 8 }}>
                                  <StatCard
                                    label="DZ Loss Share"
                                    primary={agg.turnover_ratio.dz_loss_share === null ? '—' : `${(agg.turnover_ratio.dz_loss_share * 100).toFixed(1)}%`}
                                  />
                                  <StatCard
                                    label="OZ Recovery Share"
                                    primary={agg.turnover_ratio.oz_recovery_share === null ? '—' : `${(agg.turnover_ratio.oz_recovery_share * 100).toFixed(1)}%`}
                                  />
                                </div>
                              </div>
                            )}

                            {agg.danger_share && agg.danger_share.games > 0 && (
                              <div style={{ marginTop: 16 }}>
                                <h3 style={{ fontSize: 14, marginBottom: 8, color: 'var(--text-secondary)' }}>
                                  Danger-Zone Shot Share
                                </h3>
                                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: 8 }}>
                                  <StatCard
                                    label="Share of Team HD Shots"
                                    primary={agg.danger_share.share_pct === null ? '—' : `${(agg.danger_share.share_pct * 100).toFixed(1)}%`}
                                  />
                                  <StatCard
                                    label="HD Shots/60"
                                    primary={agg.danger_share.shots_per_60 === null ? '—' : agg.danger_share.shots_per_60.toFixed(2)}
                                  />
                                </div>
                              </div>
                            )}
                          </>
                        )
                      })()}

                      <div style={{ marginTop: 24 }}>
                        <div style={{ fontSize: 10, fontWeight: 700, letterSpacing: '0.14em', textTransform: 'uppercase', color: 'var(--text-secondary)', marginBottom: 10 }}>
                          Game Log
                        </div>
                        {detailAggs[p.id].trend.map(g => {
                          const gameFlags = detailAggs[p.id].game_flags?.[g.game_id] ?? []
                          return (
                            <div key={g.game_id} style={{ display: 'flex', alignItems: 'center', padding: '6px 0', borderBottom: '1px solid var(--border)', fontSize: 12 }}>
                              <div style={{ minWidth: 90, color: 'var(--text-secondary)' }}>{g.date}</div>
                              <div style={{ minWidth: 90 }}>{g.opponent}</div>
                              <div style={{ minWidth: 60 }}>{g.toi_5v5 !== null ? g.toi_5v5.toFixed(1) + ' min' : '—'}</div>
                              {gameFlags.map((f, i) => <GameFlagBadge key={i} flag={f} />)}
                            </div>
                          )
                        })}
                      </div>
                    </>
                  ) : (
                    <div style={{ fontSize: 12, color: 'var(--text-secondary)', fontStyle: 'italic' }}>
                      Loading detail…
                    </div>
                  )}
                </div>
              )}
            </div>
          )
        })}
      </div>
    </>
  )
}
