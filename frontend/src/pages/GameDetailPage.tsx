import { useState, useEffect, useRef } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import {
  getGame, updateGame, getPlayers,
  getTeamStats, saveTeamStats,
  getPlayerGameStats, savePlayerGameStats,
} from '../api/client'
import type { Game, Player, TeamGameStats, PlayerGameStats } from '../types'
import ToiInput from '../components/ToiInput'

// Decimal minutes <-> MM:SS (for TOI fields stored as decimal minutes in DB)
function minsToMMSS(decMins: string | number | null): string {
  if (decMins === null || decMins === undefined || decMins === '') return ''
  const v = typeof decMins === 'string' ? parseFloat(decMins) : decMins
  if (isNaN(v)) return ''
  const totalSecs = Math.round(v * 60)
  const m = Math.floor(totalSecs / 60)
  const s = totalSecs % 60
  return `${m}:${s.toString().padStart(2, '0')}`
}

function mmssToMins(str: string): string {
  if (!str.trim()) return ''
  const parts = str.split(':')
  if (parts.length === 2) {
    const m = parseInt(parts[0], 10)
    const s = parseInt(parts[1], 10)
    if (!isNaN(m) && !isNaN(s)) return String(m + s / 60)
  }
  const n = parseFloat(str)
  return isNaN(n) ? '' : String(n)
}

// Seconds <-> MM:SS (for median_shift_seconds stored as seconds in DB)
function secsToMMSS(s: number | null): string {
  if (s === null || s === undefined) return ''
  const m = Math.floor(s / 60)
  const sec = Math.round(s % 60)
  return `${m}:${sec.toString().padStart(2, '0')}`
}

function mmssToSecs(str: string): number | null {
  if (!str.trim()) return null
  const parts = str.split(':')
  if (parts.length === 2) {
    const m = parseInt(parts[0], 10)
    const s = parseInt(parts[1], 10)
    if (!isNaN(m) && !isNaN(s)) return m * 60 + s
  }
  const n = parseFloat(str)
  return isNaN(n) ? null : n
}

function n(v: number | null | undefined): string {
  return v !== null && v !== undefined ? String(v) : ''
}

function p(s: string): number | null {
  if (s.trim() === '') return null
  const v = parseFloat(s)
  return isNaN(v) ? null : v
}

type Tab = 'info' | 'team' | 'players'
type PlayerFilter = 'all' | 'forwards' | 'defenders'
const PLAYER_FILTERS: { key: PlayerFilter; label: string }[] = [
  { key: 'all',       label: 'All' },
  { key: 'forwards',  label: 'Forwards' },
  { key: 'defenders', label: 'Defenders' },
]

// Table cell styles
const TH: React.CSSProperties = {
  padding: '5px 6px',
  fontSize: 9,
  fontWeight: 700,
  letterSpacing: '0.06em',
  textTransform: 'uppercase',
  color: 'var(--text-secondary)',
  background: 'var(--surface)',
  border: '1px solid var(--border)',
  textAlign: 'center',
  whiteSpace: 'nowrap',
  verticalAlign: 'middle',
}

const TH_GROUP: React.CSSProperties = {
  padding: '4px 8px',
  fontSize: 8,
  fontWeight: 700,
  letterSpacing: '0.1em',
  textTransform: 'uppercase',
  textAlign: 'center',
  border: '1px solid var(--border)',
  verticalAlign: 'middle',
}

const TD: React.CSSProperties = {
  padding: '3px 4px',
  border: '1px solid var(--border)',
  verticalAlign: 'middle',
}

const NUM_INPUT: React.CSSProperties = {
  width: '100%',
  minWidth: 52,
  padding: '3px 4px',
  textAlign: 'center',
  fontSize: 11,
}

const TEXT_INPUT: React.CSSProperties = {
  width: '100%',
  minWidth: 54,
  padding: '3px 4px',
  textAlign: 'center',
  fontSize: 11,
}

export default function GameDetailPage() {
  const { id } = useParams<{ id: string }>()
  const gameId = Number(id)
  const navigate = useNavigate()

  const [game, setGame] = useState<Game | null>(null)
  const [players, setPlayers] = useState<Player[]>([])
  const [tab, setTab] = useState<Tab>('team')

  // Game info form
  const [gameForm, setGameForm] = useState({ date: '', opponent: '', is_home: true, season: '', notes: '' })
  const [gameInfoSaved, setGameInfoSaved] = useState(false)

  // Team stats form
  const [ts, setTs] = useState<Record<string, string>>({})
  const [tsSaved, setTsSaved] = useState(false)
  const [tsSaving, setTsSaving] = useState(false)

  // Player stats — all loaded eagerly when tab opens
  const [playerFilter, setPlayerFilter] = useState<PlayerFilter>('all')
  const [playerForms, setPlayerForms] = useState<Record<number, Record<string, string>>>({})
  const [savedPlayers, setSavedPlayers] = useState<Set<number>>(new Set())
  const [savingPlayer, setSavingPlayer] = useState<number | null>(null)
  const [savingAll, setSavingAll] = useState(false)
  const loadedIds = useRef(new Set<number>())

  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  // Load game, players, team stats on mount
  useEffect(() => {
    Promise.all([
      getGame(gameId),
      getPlayers(),
      getTeamStats(gameId),
    ]).then(([g, ps, tgs]) => {
      setGame(g)
      setGameForm({ date: g.date, opponent: g.opponent, is_home: g.is_home, season: g.season, notes: g.notes ?? '' })
      setPlayers(ps.filter(p => p.active))
      const init: Record<string, string> = {}
      if (tgs) {
        const fields = Object.keys(tgs) as (keyof TeamGameStats)[]
        fields.forEach(f => { if (f !== 'game_id') init[f] = n(tgs[f] as number | null) })
      }
      setTs(init)
    }).catch(() => setError('Failed to load game data.'))
      .finally(() => setLoading(false))
  }, [gameId])

  // Eagerly load all player forms when switching to players tab
  useEffect(() => {
    if (tab !== 'players' || players.length === 0) return
    const toLoad = players.filter(p => !loadedIds.current.has(p.id))
    if (toLoad.length === 0) return

    Promise.all(toLoad.map(async player => {
      loadedIds.current.add(player.id)
      const existing = await getPlayerGameStats(gameId, player.id)
      const form: Record<string, string> = {
        toi_5v5: '',
        cf60: '0', ca60: '0',
        ff60: '0', fa60: '0',
        sf60: '0', sa60: '0',
        xgf60: '0', xga60: '0',
        icf: '0', isf: '0',
        median_shift_seconds: '',
        personal_draws_taken: '0', personal_draws_won: '0',
        team_fo_wins_on_ice: '0', team_fo_losses_on_ice: '0',
      }
      if (existing) {
        Object.keys(form).forEach(k => {
          const v = existing[k as keyof PlayerGameStats]
          if (k === 'toi_5v5') {
            form[k] = minsToMMSS(v as number | null)
          } else if (k === 'median_shift_seconds') {
            form[k] = secsToMMSS(v as number | null)
          } else {
            form[k] = n(v as number | null)
          }
        })
        setSavedPlayers(s => new Set([...s, player.id]))
      }
      return { id: player.id, form }
    })).then(results => {
      setPlayerForms(f => {
        const next = { ...f }
        results.forEach(r => { next[r.id] = r.form })
        return next
      })
    })
  }, [tab, players, gameId])

  async function saveGameInfo() {
    if (!game) return
    await updateGame(game.id, { ...gameForm, notes: gameForm.notes || null })
    setGameInfoSaved(true)
    setTimeout(() => setGameInfoSaved(false), 2000)
  }

  async function saveTeam() {
    setTsSaving(true)
    try {
      const payload: Partial<TeamGameStats> = {}
      Object.entries(ts).forEach(([k, v]) => {
        (payload as Record<string, unknown>)[k] = p(v)
      })
      await saveTeamStats(gameId, payload)
      setTsSaved(true)
      setTimeout(() => setTsSaved(false), 2000)
    } finally {
      setTsSaving(false)
    }
  }

  async function savePlayer(playerId: number) {
    setSavingPlayer(playerId)
    try {
      const form = playerForms[playerId] ?? {}
      const payload: Partial<PlayerGameStats> = {}
      Object.keys(form).forEach(k => {
        if (k === 'toi_5v5') {
          const mins = mmssToMins(form[k])
          ;(payload as Record<string, unknown>)[k] = p(mins)
        } else if (k === 'median_shift_seconds') {
          ;(payload as Record<string, unknown>)[k] = mmssToSecs(form[k])
        } else {
          ;(payload as Record<string, unknown>)[k] = p(form[k])
        }
      })
      await savePlayerGameStats(gameId, playerId, payload)
      setSavedPlayers(s => new Set([...s, playerId]))
    } finally {
      setSavingPlayer(null)
    }
  }

  async function saveAllPlayers() {
    setSavingAll(true)
    try {
      const visible = players.filter(p => {
        if (playerFilter === 'forwards')  return p.position === 'F'
        if (playerFilter === 'defenders') return p.position === 'D'
        return true
      })
      for (const player of visible) {
        if (playerForms[player.id]) await savePlayer(player.id)
      }
    } finally {
      setSavingAll(false)
    }
  }

  function setTsField(k: string, v: string) { setTs(f => ({ ...f, [k]: v })); setTsSaved(false) }
  function setPf(playerId: number, k: string, v: string) {
    setPlayerForms(f => ({ ...f, [playerId]: { ...f[playerId], [k]: v } }))
    setSavedPlayers(s => { const next = new Set(s); next.delete(playerId); return next })
  }

  function numField(key: string, label: string, placeholder = '0') {
    return (
      <div className="form-field">
        <label>{label}</label>
        <input type="number" value={ts[key] ?? ''} onChange={e => setTsField(key, e.target.value)} placeholder={placeholder} step="any" />
      </div>
    )
  }

  if (loading) return <div className="loading">Loading…</div>
  if (error) return <div className="alert alert-error" style={{ margin: 40 }}>{error}</div>
  if (!game) return null

  const visiblePlayers = players.filter(p => {
    if (playerFilter === 'forwards')  return p.position === 'F'
    if (playerFilter === 'defenders') return p.position === 'D'
    return true
  })

  return (
    <>
      <div className="page-header">
        <div>
          <div style={{ fontSize: 12, color: 'var(--text-secondary)', marginBottom: 4, cursor: 'pointer' }} onClick={() => navigate('/games')}>
            ← Games
          </div>
          <div className="page-title">{game.opponent}</div>
          <div className="page-subtitle">
            {game.date} · {game.is_home ? 'Home' : 'Away'} · {game.season}
          </div>
        </div>
      </div>

      {/* Tab bar */}
      <div style={{ display: 'flex', gap: 0, borderBottom: '1px solid var(--border)', marginBottom: 24 }}>
        {(['info', 'team', 'players'] as Tab[]).map(t => (
          <button
            key={t}
            onClick={() => setTab(t)}
            style={{
              padding: '10px 20px',
              background: 'none',
              color: tab === t ? 'var(--text)' : 'var(--text-secondary)',
              borderBottom: tab === t ? '2px solid var(--crimson)' : '2px solid transparent',
              fontWeight: tab === t ? 600 : 400,
              fontSize: 13,
              textTransform: 'capitalize',
              transition: 'all 0.15s',
            }}
          >
            {t === 'info' ? 'Game Info' : t === 'team' ? 'Team Stats' : 'Player Stats'}
          </button>
        ))}
      </div>

      {/* ── Game Info ── */}
      {tab === 'info' && (
        <div className="card" style={{ maxWidth: 560 }}>
          <div className="form-grid" style={{ marginBottom: 14 }}>
            <div className="form-field">
              <label>Date</label>
              <input type="date" value={gameForm.date} onChange={e => setGameForm(f => ({ ...f, date: e.target.value }))} />
            </div>
            <div className="form-field">
              <label>Season</label>
              <input value={gameForm.season} onChange={e => setGameForm(f => ({ ...f, season: e.target.value }))} />
            </div>
          </div>
          <div className="form-field" style={{ marginBottom: 14 }}>
            <label>Opponent</label>
            <input value={gameForm.opponent} onChange={e => setGameForm(f => ({ ...f, opponent: e.target.value }))} />
          </div>
          <div className="form-field" style={{ marginBottom: 14 }}>
            <label>Location</label>
            <select value={gameForm.is_home ? 'home' : 'away'} onChange={e => setGameForm(f => ({ ...f, is_home: e.target.value === 'home' }))}>
              <option value="home">Home</option>
              <option value="away">Away</option>
            </select>
          </div>
          <div className="form-field" style={{ marginBottom: 20 }}>
            <label>Notes</label>
            <input value={gameForm.notes} onChange={e => setGameForm(f => ({ ...f, notes: e.target.value }))} placeholder="Optional notes" />
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
            <button className="btn btn-primary" onClick={saveGameInfo}>Save Game Info</button>
            {gameInfoSaved && <span className="badge badge-saved">Saved ✓</span>}
          </div>
        </div>
      )}

      {/* ── Team Stats ── */}
      {tab === 'team' && (
        <>
          <div className="section-divider">Game Time & 5v5 TOI Estimation</div>
          <div style={{ fontSize: 12, color: 'var(--text-secondary)', marginBottom: 12 }}>
            5v5 TOI is estimated as: Total Game Time − Power Play TOI − Penalty Kill TOI − Other. Source: Data Cockpit Team tab (Special Teams section for PP/PK TOI).
          </div>
          <div className="form-grid" style={{ marginBottom: 10 }}>
            <div className="form-field">
              <label>Total Game Time (min : sec)</label>
              <ToiInput valueMinutes={ts['total_game_time'] ?? '60'} onChange={v => setTsField('total_game_time', v)} placeholder="60" />
            </div>
            <div className="form-field">
              <label>Other Strength States TOI (min : sec)</label>
              <ToiInput valueMinutes={ts['other_toi'] ?? '0'} onChange={v => setTsField('other_toi', v)} placeholder="0" />
            </div>
          </div>
          {(() => {
            const total = parseFloat(ts['total_game_time'] ?? '60') || 60
            const pp = parseFloat(ts['toi_pp'] ?? '0') || 0
            const pk = parseFloat(ts['toi_pk'] ?? '0') || 0
            const other = parseFloat(ts['other_toi'] ?? '0') || 0
            const est = Math.max(total - pp - pk - other, 0)
            return (
              <div style={{ background: 'var(--surface)', border: '1px solid var(--border)', borderRadius: 8, padding: '10px 14px', marginBottom: 20, display: 'flex', alignItems: 'center', gap: 12 }}>
                <span style={{ fontSize: 11, fontWeight: 700, letterSpacing: '0.08em', textTransform: 'uppercase', color: 'var(--text-secondary)' }}>Est. 5v5 TOI</span>
                <span style={{ fontSize: 20, fontWeight: 700, color: 'var(--ice)' }}>{est.toFixed(1)} min</span>
                <span style={{ fontSize: 11, color: 'var(--text-secondary)' }}>{total} − {pp} (PP) − {pk} (PK) − {other} (other)</span>
              </div>
            )
          })()}

          <div className="section-divider">5v5 Core</div>
          <div style={{ fontSize: 12, color: 'var(--text-secondary)', marginBottom: 12 }}>
            CF/CA from Data Cockpit's "Shot Attempts – Corsi" view (Strength State: 5-5). xGF/xGA from Summary tab.
          </div>
          <div className="form-grid-3" style={{ marginBottom: 14 }}>
            {numField('cf_for_5v5', 'CF For')}
            {numField('cf_against_5v5', 'CF Against')}
          </div>
          <div className="form-grid-3" style={{ marginBottom: 20 }}>
            {numField('ff_for_5v5', 'FF For')}
            {numField('ff_against_5v5', 'FF Against')}
            <div style={{ display: 'flex', flexDirection: 'column' }}>{/* spacer */}</div>
            {numField('xgf_5v5', 'xGF')}
            {numField('xga_5v5', 'xGA')}
          </div>

          <div className="section-divider">Special Teams</div>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 24, marginBottom: 20 }}>
            <div>
              <div style={{ fontSize: 11, fontWeight: 700, letterSpacing: '0.08em', textTransform: 'uppercase', color: 'var(--gold)', marginBottom: 10 }}>
                Power Play (5v4) — from Team tab
              </div>
              <div className="form-field" style={{ marginBottom: 10 }}>
                <label>PP TOI (min : sec)</label>
                <ToiInput valueMinutes={ts['toi_pp'] ?? ''} onChange={v => setTsField('toi_pp', v)} placeholder="0" />
              </div>
              <div className="form-grid" style={{ marginBottom: 10 }}>
                {numField('cf_for_5v4', 'CF For')}
                {numField('cf_against_5v4', 'CF Against')}
              </div>
              <div className="form-grid">
                {numField('xgf_5v4', 'xGF')}
                {numField('xga_5v4', 'xGA')}
              </div>
            </div>
            <div>
              <div style={{ fontSize: 11, fontWeight: 700, letterSpacing: '0.08em', textTransform: 'uppercase', color: 'var(--ice)', marginBottom: 10 }}>
                Penalty Kill (4v5) — from Team tab
              </div>
              <div className="form-field" style={{ marginBottom: 10 }}>
                <label>PK TOI (min : sec)</label>
                <ToiInput valueMinutes={ts['toi_pk'] ?? ''} onChange={v => setTsField('toi_pk', v)} placeholder="0" />
              </div>
              <div className="form-grid" style={{ marginBottom: 10 }}>
                {numField('cf_for_4v5', 'CF For')}
                {numField('cf_against_4v5', 'CF Against')}
              </div>
              <div className="form-grid">
                {numField('xgf_4v5', 'xGF')}
                {numField('xga_4v5', 'xGA')}
              </div>
            </div>
          </div>

          <div className="section-divider">Attack Scenario Mix (by Expected-Goal Share)</div>
          <div style={{ fontSize: 12, color: 'var(--text-secondary)', marginBottom: 12 }}>
            Source: Data Cockpit Attack Scenarios tab, filtered to Strength State 5-5. Enter xGF per scenario — 49ing exposes xG totals only, not shot-attempt counts, so the mix is xG-weighted (scoring threat share), not frequency-weighted.
          </div>
          <div className="card" style={{ marginBottom: 20 }}>
            <table style={{ width: '100%', borderCollapse: 'collapse' }}>
              <thead>
                <tr>
                  <th style={{ textAlign: 'left', fontSize: 10, fontWeight: 700, letterSpacing: '0.08em', textTransform: 'uppercase', color: 'var(--text-secondary)', padding: '6px 10px', borderBottom: '1px solid var(--border)' }}>Scenario</th>
                  <th style={{ fontSize: 10, fontWeight: 700, letterSpacing: '0.08em', textTransform: 'uppercase', color: 'var(--text-secondary)', padding: '6px 10px', borderBottom: '1px solid var(--border)', textAlign: 'center' }}>xGF (our scenarios)</th>
                </tr>
              </thead>
              <tbody>
                {[
                  ['Rush', 'rush_xgf', 'Entry → shot within 5 sec'],
                  ['OZ Forecheck', 'oz_fc_xgf', 'Forecheck possession → shot within 5 sec'],
                  ['OZ Faceoff', 'oz_fo_xgf', 'OZ faceoff win → shot within 5 sec'],
                  ['Sustained Pos.', 'sust_pos_xgf', '5+ sec continuous OZ possession → shot'],
                ].map(([label, key, desc]) => (
                  <tr key={String(label)}>
                    <td style={{ padding: '8px 10px', borderBottom: '1px solid var(--border)' }}>
                      <div style={{ fontWeight: 600, fontSize: 13 }}>{label}</div>
                      <div style={{ fontSize: 10, color: 'var(--text-secondary)', marginTop: 2 }}>{desc}</div>
                    </td>
                    <td style={{ padding: '8px 10px', borderBottom: '1px solid var(--border)', width: 180 }}>
                      <input type="number" value={ts[String(key)] ?? ''} onChange={e => setTsField(String(key), e.target.value)} placeholder="0.000" step="any" style={{ textAlign: 'center' }} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 28 }}>
            <button className="btn btn-primary" onClick={saveTeam} disabled={tsSaving}>
              {tsSaving ? 'Saving…' : 'Save Team Stats'}
            </button>
            {tsSaved && <span className="badge badge-saved">Saved ✓</span>}
          </div>
        </>
      )}

      {/* ── Player Stats — spreadsheet view ── */}
      {tab === 'players' && (
        <>
          {/* Toolbar */}
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 14 }}>
            <div style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
              {PLAYER_FILTERS.map(f => (
                <button
                  key={f.key}
                  onClick={() => setPlayerFilter(f.key)}
                  style={{
                    padding: '5px 12px',
                    borderRadius: 6,
                    fontSize: 12,
                    fontWeight: 600,
                    border: `1px solid ${playerFilter === f.key ? 'var(--crimson)' : 'var(--border)'}`,
                    background: playerFilter === f.key ? 'var(--crimson-dim)' : 'transparent',
                    color: playerFilter === f.key ? 'var(--crimson)' : 'var(--text-secondary)',
                    cursor: 'pointer',
                    transition: 'all 0.15s',
                  }}
                >
                  {f.label}
                </button>
              ))}
              <span style={{ fontSize: 11, color: 'var(--text-secondary)', marginLeft: 4 }}>
                {visiblePlayers.length} players · 5v5 on-ice per 60 min · MM:SS for time fields
              </span>
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
              {(savingPlayer !== null || savingAll) && (
                <span style={{ fontSize: 11, color: 'var(--text-secondary)' }}>Saving…</span>
              )}
              <button
                className="btn btn-primary"
                onClick={saveAllPlayers}
                disabled={savingAll || savingPlayer !== null}
              >
                Save All
              </button>
            </div>
          </div>

          {players.length === 0 && (
            <div className="alert alert-error">No active players on roster. Add players first.</div>
          )}

          <div style={{ overflowX: 'auto' }}>
            <table style={{ borderCollapse: 'collapse', fontSize: 12 }}>
              <thead>
                {/* Group header row */}
                <tr>
                  <th rowSpan={2} style={{ ...TH, textAlign: 'left', minWidth: 140, position: 'sticky', left: 0, zIndex: 2 }}>
                    Player
                  </th>
                  <th rowSpan={2} style={{ ...TH, minWidth: 62 }}>
                    TOI<br />
                    <span style={{ fontWeight: 400, fontSize: 8, letterSpacing: 0, textTransform: 'none' }}>MM:SS</span>
                  </th>
                  <th colSpan={4} style={{ ...TH_GROUP, background: '#6b1220', color: '#fff' }}>
                    Generated Output
                  </th>
                  <th colSpan={4} style={{ ...TH_GROUP, background: '#1a3a5c', color: '#fff' }}>
                    Allowed Output
                  </th>
                  <th colSpan={3} style={{ ...TH_GROUP, background: 'var(--surface)' }}>
                    Individual
                  </th>
                  <th
                    colSpan={4}
                    style={{ ...TH_GROUP, background: 'var(--surface)', borderLeft: '2px solid var(--gold)', color: 'var(--gold)' }}
                  >
                    Faceoffs <span style={{ fontWeight: 400, color: 'var(--text-secondary)' }}>(Forwards)</span>
                  </th>
                  <th rowSpan={2} style={{ ...TH, minWidth: 48 }} />
                </tr>
                {/* Sub-header: field names */}
                <tr>
                  <th style={{ ...TH, color: 'var(--crimson)' }}>xGF60</th>
                  <th style={TH}>CF60</th>
                  <th style={TH}>FF60</th>
                  <th style={TH}>SF60</th>
                  <th style={{ ...TH, color: 'var(--ice)' }}>xGA60</th>
                  <th style={TH}>CA60</th>
                  <th style={TH}>FA60</th>
                  <th style={TH}>SA60</th>
                  <th style={TH}>ICF</th>
                  <th style={TH}>ISF</th>
                  <th style={{ ...TH, minWidth: 62 }}>
                    Shift<br />
                    <span style={{ fontWeight: 400, fontSize: 8, letterSpacing: 0, textTransform: 'none' }}>MM:SS</span>
                  </th>
                  <th style={{ ...TH, borderLeft: '2px solid var(--gold)' }}>Taken</th>
                  <th style={TH}>Won</th>
                  <th style={TH}>TmW</th>
                  <th style={TH}>TmL</th>
                </tr>
              </thead>
              <tbody>
                {visiblePlayers.map(player => {
                  const form = playerForms[player.id]
                  const saved = savedPlayers.has(player.id)
                  const isSaving = savingPlayer === player.id
                  return (
                    <tr
                      key={player.id}
                      style={{
                        background: saved ? 'rgba(34, 197, 94, 0.05)' : undefined,
                        transition: 'background 0.25s',
                      }}
                    >
                      {/* Player name — sticky */}
                      <td style={{ ...TD, padding: '5px 8px', position: 'sticky', left: 0, background: saved ? 'rgba(34,197,94,0.05)' : 'var(--bg)', zIndex: 1, minWidth: 140 }}>
                        <div style={{ fontWeight: 600, fontSize: 12, whiteSpace: 'nowrap' }}>{player.name}</div>
                        <div style={{ fontSize: 10, color: 'var(--text-secondary)', display: 'flex', alignItems: 'center', gap: 5, marginTop: 1 }}>
                          <span>{player.position}{player.number ? ` #${player.number}` : ''}</span>
                          {player.is_center && <span style={{ color: 'var(--crimson)', fontWeight: 700 }}>C</span>}
                          {saved && <span style={{ color: 'var(--green)', fontWeight: 700, marginLeft: 2 }}>✓</span>}
                        </div>
                      </td>

                      {/* TOI */}
                      <td style={TD}>
                        {!form
                          ? <span style={{ color: 'var(--text-secondary)', fontSize: 10, padding: '0 4px' }}>…</span>
                          : <input type="text" value={form.toi_5v5} onChange={e => setPf(player.id, 'toi_5v5', e.target.value)} placeholder="8:30" style={TEXT_INPUT} />
                        }
                      </td>

                      {/* Generated Output: xGF60, CF60, FF60, SF60 */}
                      {(['xgf60', 'cf60', 'ff60', 'sf60'] as const).map(k => (
                        <td key={k} style={TD}>
                          {!form
                            ? <span style={{ color: 'var(--text-secondary)', fontSize: 10, padding: '0 4px' }}>…</span>
                            : <input type="number" value={form[k] ?? '0'} onChange={e => setPf(player.id, k, e.target.value)} placeholder="0" step="any" style={NUM_INPUT} />
                          }
                        </td>
                      ))}

                      {/* Allowed Output: xGA60, CA60, FA60, SA60 */}
                      {(['xga60', 'ca60', 'fa60', 'sa60'] as const).map(k => (
                        <td key={k} style={TD}>
                          {!form
                            ? <span style={{ color: 'var(--text-secondary)', fontSize: 10, padding: '0 4px' }}>…</span>
                            : <input type="number" value={form[k] ?? '0'} onChange={e => setPf(player.id, k, e.target.value)} placeholder="0" step="any" style={NUM_INPUT} />
                          }
                        </td>
                      ))}

                      {/* Individual: ICF, ISF */}
                      {(['icf', 'isf'] as const).map(k => (
                        <td key={k} style={TD}>
                          {!form
                            ? <span style={{ color: 'var(--text-secondary)', fontSize: 10, padding: '0 4px' }}>…</span>
                            : <input type="number" value={form[k] ?? '0'} onChange={e => setPf(player.id, k, e.target.value)} placeholder="0" step="any" style={NUM_INPUT} />
                          }
                        </td>
                      ))}

                      {/* Shift */}
                      <td style={TD}>
                        {!form
                          ? <span style={{ color: 'var(--text-secondary)', fontSize: 10, padding: '0 4px' }}>…</span>
                          : <input type="text" value={form.median_shift_seconds} onChange={e => setPf(player.id, 'median_shift_seconds', e.target.value)} placeholder="0:45" style={TEXT_INPUT} />
                        }
                      </td>

                      {/* Faceoffs — enabled for centers only */}
                      {(['personal_draws_taken', 'personal_draws_won', 'team_fo_wins_on_ice', 'team_fo_losses_on_ice'] as const).map((k, i) => (
                        <td key={k} style={{ ...TD, ...(i === 0 ? { borderLeft: '2px solid var(--gold)' } : {}) }}>
                          {!form
                            ? <span style={{ color: 'var(--text-secondary)', fontSize: 10, padding: '0 4px' }}>…</span>
                            : <input
                                type="number"
                                value={form[k] ?? '0'}
                                onChange={e => setPf(player.id, k, e.target.value)}
                                placeholder="0"
                                step="any"
                                disabled={player.position !== 'F'}
                                style={{
                                  ...NUM_INPUT,
                                  opacity: player.position === 'F' ? 1 : 0.25,
                                  background: player.position === 'F' ? undefined : 'var(--surface)',
                                  cursor: player.position === 'F' ? undefined : 'not-allowed',
                                }}
                              />
                          }
                        </td>
                      ))}

                      {/* Per-row save */}
                      <td style={{ ...TD, padding: '4px 6px' }}>
                        <button
                          className="btn btn-primary btn-sm"
                          onClick={() => savePlayer(player.id)}
                          disabled={isSaving || !form}
                          style={{ fontSize: 10, padding: '4px 8px', whiteSpace: 'nowrap' }}
                        >
                          {isSaving ? '…' : 'Save'}
                        </button>
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>

          {/* Bottom Save All */}
          <div style={{ display: 'flex', justifyContent: 'flex-end', marginTop: 16, gap: 10, alignItems: 'center' }}>
            {savingAll && <span style={{ fontSize: 11, color: 'var(--text-secondary)' }}>Saving all players…</span>}
            <button
              className="btn btn-primary"
              onClick={saveAllPlayers}
              disabled={savingAll || savingPlayer !== null}
            >
              Save All
            </button>
          </div>
        </>
      )}
    </>
  )
}
