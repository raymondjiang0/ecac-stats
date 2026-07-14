import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { getGames, createGame, deleteGame, getAllPlayerStats } from '../api/client'
import type { Game } from '../types'

const EMPTY_FORM = {
  date: new Date().toISOString().slice(0, 10),
  opponent: '',
  is_home: true,
  season: '2025-26',
  notes: '',
}

export default function GamesPage() {
  const [games, setGames] = useState<Game[]>([])
  const [playerCounts, setPlayerCounts] = useState<Record<number, number>>({})
  const [showModal, setShowModal] = useState(false)
  const [form, setForm] = useState(EMPTY_FORM)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')
  const navigate = useNavigate()

  useEffect(() => {
    getGames()
      .then(async gs => {
        setGames(gs)
        const counts: Record<number, number> = {}
        await Promise.all(
          gs.map(async g => {
            const stats = await getAllPlayerStats(g.id)
            counts[g.id] = stats.filter(s => s.toi_5v5 && s.toi_5v5 > 0).length
          })
        )
        setPlayerCounts(counts)
      })
      .finally(() => setLoading(false))
  }, [])

  async function handleCreate() {
    if (!form.opponent.trim()) { setError('Opponent is required'); return }
    setSaving(true)
    try {
      const created = await createGame({ ...form, notes: form.notes || null })
      setGames(gs => [created, ...gs])
      setShowModal(false)
      navigate(`/games/${created.id}`)
    } catch {
      setError('Failed to create game.')
    } finally {
      setSaving(false)
    }
  }

  async function handleDelete(g: Game, e: React.MouseEvent) {
    e.stopPropagation()
    if (!confirm(`Delete game vs ${g.opponent} on ${g.date}? This removes all associated stats.`)) return
    await deleteGame(g.id)
    setGames(gs => gs.filter(x => x.id !== g.id))
  }

  // Group games by season, most-recent season first
  const bySeason: Record<string, Game[]> = {}
  for (const g of games) {
    if (!bySeason[g.season]) bySeason[g.season] = []
    bySeason[g.season].push(g)
  }
  const seasons = Object.keys(bySeason).sort((a, b) => b.localeCompare(a))

  if (loading) return <div className="loading">Loading games…</div>

  return (
    <>
      <div className="page-header">
        <div>
          <div className="page-title">Games</div>
          <div className="page-subtitle">
            {games.length} game{games.length !== 1 ? 's' : ''} across {seasons.length} season{seasons.length !== 1 ? 's' : ''}
          </div>
        </div>
        <button className="btn btn-primary" onClick={() => { setForm(EMPTY_FORM); setError(''); setShowModal(true) }}>
          + Log Game
        </button>
      </div>

      {games.length === 0 ? (
        <div className="empty-state">
          <div className="empty-state-icon">◈</div>
          <div className="empty-state-title">No games logged yet</div>
          <div className="empty-state-body">Create your first game entry to start tracking stats.</div>
        </div>
      ) : (
        seasons.map(season => (
          <div key={season} style={{ marginBottom: 32 }}>
            <div style={{
              display: 'flex',
              alignItems: 'center',
              gap: 14,
              marginBottom: 12,
            }}>
              <div style={{
                fontFamily: "'Playfair Display', Georgia, serif",
                fontSize: 20,
                fontWeight: 900,
                color: 'var(--text)',
              }}>
                {season}
              </div>
              <div style={{
                fontSize: 11,
                fontWeight: 600,
                letterSpacing: '0.1em',
                textTransform: 'uppercase',
                color: 'var(--text-secondary)',
                paddingTop: 2,
              }}>
                {bySeason[season].length} game{bySeason[season].length !== 1 ? 's' : ''}
              </div>
              <div style={{ flex: 1, height: 1, background: 'var(--border)' }} />
            </div>

            <div className="card" style={{ padding: 0 }}>
              <table className="data-table">
                <thead>
                  <tr>
                    <th>Date</th>
                    <th>Opponent</th>
                    <th>Location</th>
                    <th>Players Entered</th>
                    <th></th>
                  </tr>
                </thead>
                <tbody>
                  {bySeason[season]
                    .sort((a, b) => b.date.localeCompare(a.date))
                    .map(g => (
                    <tr
                      key={g.id}
                      style={{ cursor: 'pointer' }}
                      onClick={() => navigate(`/games/${g.id}`)}
                    >
                      <td style={{ fontWeight: 600 }}>{g.date}</td>
                      <td>{g.opponent}</td>
                      <td>
                        <span className={`badge ${g.is_home ? 'badge-home' : 'badge-away'}`}>
                          {g.is_home ? 'Home' : 'Away'}
                        </span>
                      </td>
                      <td>
                        <span style={{ fontSize: 12, color: playerCounts[g.id] ? 'var(--green)' : 'var(--text-secondary)' }}>
                          {playerCounts[g.id] ?? 0} player{playerCounts[g.id] !== 1 ? 's' : ''}
                        </span>
                      </td>
                      <td style={{ textAlign: 'right' }}>
                        <button className="btn btn-ghost btn-sm" onClick={e => { e.stopPropagation(); navigate(`/games/${g.id}`) }} style={{ marginRight: 6 }}>
                          Enter Stats
                        </button>
                        <button className="btn btn-danger btn-sm" onClick={e => handleDelete(g, e)}>
                          Delete
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        ))
      )}

      {showModal && (
        <div className="modal-overlay" onClick={e => e.target === e.currentTarget && setShowModal(false)}>
          <div className="modal">
            <div className="modal-title">Log New Game</div>
            {error && <div className="alert alert-error">{error}</div>}

            <div className="form-grid" style={{ marginBottom: 14 }}>
              <div className="form-field">
                <label>Date *</label>
                <input type="date" value={form.date} onChange={e => setForm(f => ({ ...f, date: e.target.value }))} />
              </div>
              <div className="form-field">
                <label>Season</label>
                <input value={form.season} onChange={e => setForm(f => ({ ...f, season: e.target.value }))} placeholder="2025-26" />
              </div>
            </div>

            <div className="form-field" style={{ marginBottom: 14 }}>
              <label>Opponent *</label>
              <input value={form.opponent} onChange={e => setForm(f => ({ ...f, opponent: e.target.value }))} placeholder="e.g. Princeton" />
            </div>

            <div className="form-field" style={{ marginBottom: 14 }}>
              <label>Location</label>
              <select value={form.is_home ? 'home' : 'away'} onChange={e => setForm(f => ({ ...f, is_home: e.target.value === 'home' }))}>
                <option value="home">Home</option>
                <option value="away">Away</option>
              </select>
            </div>

            <div className="form-field" style={{ marginBottom: 14 }}>
              <label>Notes (optional)</label>
              <input value={form.notes} onChange={e => setForm(f => ({ ...f, notes: e.target.value }))} placeholder="e.g. ECAC conference game" />
            </div>

            <div className="modal-actions">
              <button className="btn btn-ghost" onClick={() => setShowModal(false)}>Cancel</button>
              <button className="btn btn-primary" onClick={handleCreate} disabled={saving}>
                {saving ? 'Creating…' : 'Create Game'}
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  )
}
