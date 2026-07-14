import { useState, useEffect, useCallback } from 'react'
import { getPlayers, getAllPlayerAggStats, getGames, downloadPlayerReport, downloadTeamReport, exportAllData } from '../api/client'
import type { Player, PlayerAggStats, Game } from '../types'
import SmallSampleBadge from '../components/SmallSampleBadge'

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
    getAllPlayerAggStats(dateFrom, dateTo)
      .then(aggs => {
        const map: Record<number, PlayerAggStats> = {}
        aggs.forEach(a => { map[a.player_id] = a })
        setAggStats(map)
      })
      .finally(() => setStatsLoading(false))
  }, [dateFrom, dateTo])

  useEffect(() => {
    if (!loading) refreshStats()
  }, [loading, dateFrom, dateTo])

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

              <button
                className="btn btn-primary"
                onClick={() => downloadPlayer(p)}
                disabled={downloading === p.id || visibleGames.length === 0}
                style={{ width: '100%' }}
              >
                {downloading === p.id ? 'Generating PDF…' : 'Download Player PDF'}
              </button>
            </div>
          )
        })}
      </div>
    </>
  )
}
