import { useState, useEffect } from 'react'
import { getPlayers, createPlayer, updatePlayer, deletePlayer } from '../api/client'
import type { Player } from '../types'

const POSITIONS = ['F', 'D', 'G']
const EMPTY_FORM = { name: '', number: '', position: 'F', is_center: false, active: true }

type Filter = 'all' | 'forwards' | 'defenders'

const FILTERS: { key: Filter; label: string }[] = [
  { key: 'all',       label: 'All' },
  { key: 'forwards',  label: 'Forwards' },
  { key: 'defenders', label: 'Defenders' },
]

export default function RosterPage() {
  const [players, setPlayers] = useState<Player[]>([])
  const [filter, setFilter] = useState<Filter>('all')
  const [showModal, setShowModal] = useState(false)
  const [editing, setEditing] = useState<Player | null>(null)
  const [form, setForm] = useState(EMPTY_FORM)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    getPlayers().then(setPlayers).finally(() => setLoading(false))
  }, [])

  function openAdd() {
    setEditing(null)
    setForm(EMPTY_FORM)
    setError('')
    setShowModal(true)
  }

  function openEdit(p: Player) {
    setEditing(p)
    setForm({ name: p.name, number: p.number ?? '', position: p.position, is_center: p.is_center, active: p.active })
    setError('')
    setShowModal(true)
  }

  async function handleSave() {
    if (!form.name.trim()) { setError('Name is required'); return }
    setSaving(true)
    try {
      if (editing) {
        const updated = await updatePlayer(editing.id, { ...form, number: form.number || null })
        setPlayers(ps => ps.map(p => p.id === updated.id ? updated : p))
      } else {
        const created = await createPlayer({ ...form, number: form.number || null })
        setPlayers(ps => [...ps, created].sort((a, b) => a.name.localeCompare(b.name)))
      }
      setShowModal(false)
    } catch {
      setError('Save failed — check the server.')
    } finally {
      setSaving(false)
    }
  }

  async function handleDelete(p: Player) {
    if (!confirm(`Remove ${p.name} from roster? This deletes all their game stats.`)) return
    await deletePlayer(p.id)
    setPlayers(ps => ps.filter(x => x.id !== p.id))
  }

  async function toggleActive(p: Player) {
    const updated = await updatePlayer(p.id, { active: !p.active })
    setPlayers(ps => ps.map(x => x.id === updated.id ? updated : x))
  }

  if (loading) return <div className="loading">Loading roster…</div>

  const visible = players.filter(p => {
    if (filter === 'forwards')  return p.position === 'F'
    if (filter === 'defenders') return p.position === 'D'
    return true
  })

  return (
    <>
      <div className="page-header">
        <div>
          <div className="page-title">Roster</div>
          <div className="page-subtitle">{players.filter(p => p.active).length} active players</div>
        </div>
        <button className="btn btn-primary" onClick={openAdd}>+ Add Player</button>
      </div>

      <div style={{ display: 'flex', gap: 6, marginBottom: 16 }}>
        {FILTERS.map(f => (
          <button
            key={f.key}
            onClick={() => setFilter(f.key)}
            style={{
              padding: '6px 14px',
              borderRadius: 6,
              fontSize: 12,
              fontWeight: 600,
              border: `1px solid ${filter === f.key ? 'var(--crimson)' : 'var(--border)'}`,
              background: filter === f.key ? 'var(--crimson-dim)' : 'transparent',
              color: filter === f.key ? 'var(--crimson)' : 'var(--text-secondary)',
              cursor: 'pointer',
              transition: 'all 0.15s',
            }}
          >
            {f.label}
          </button>
        ))}
      </div>

      <div className="card">
        {visible.length === 0 ? (
          <div className="empty-state">
            <div className="empty-state-icon">⬡</div>
            <div className="empty-state-title">No players yet</div>
            <div className="empty-state-body">Add your first player to get started.</div>
          </div>
        ) : (
          <table className="data-table">
            <thead>
              <tr>
                <th>#</th>
                <th>Name</th>
                <th>Position</th>
                <th>Status</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {visible.map(p => (
                <tr key={p.id} style={{ opacity: p.active ? 1 : 0.45 }}>
                  <td style={{ color: 'var(--text-secondary)', fontSize: 12 }}>{p.number ?? '—'}</td>
                  <td>
                    <span style={{ fontWeight: 600 }}>{p.name}</span>
                    {p.is_center && (
                      <span className="badge badge-center" style={{ marginLeft: 8 }}>C</span>
                    )}
                  </td>
                  <td>
                    <span style={{ fontSize: 12, color: 'var(--text-secondary)', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.06em' }}>
                      {p.position}
                    </span>
                  </td>
                  <td>
                    <button
                      className={`badge ${p.active ? 'badge-home' : 'badge-away'}`}
                      style={{ cursor: 'pointer', border: 'none', background: 'none' }}
                      onClick={() => toggleActive(p)}
                      title="Click to toggle active/inactive"
                    >
                      {p.active ? 'Active' : 'Inactive'}
                    </button>
                  </td>
                  <td style={{ textAlign: 'right' }}>
                    <button className="btn btn-ghost btn-sm" onClick={() => openEdit(p)} style={{ marginRight: 6 }}>
                      Edit
                    </button>
                    <button className="btn btn-danger btn-sm" onClick={() => handleDelete(p)}>
                      Remove
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {showModal && (
        <div className="modal-overlay" onClick={e => e.target === e.currentTarget && setShowModal(false)}>
          <div className="modal">
            <div className="modal-title">{editing ? 'Edit Player' : 'Add Player'}</div>

            {error && <div className="alert alert-error">{error}</div>}

            <div className="form-grid" style={{ marginBottom: 14 }}>
              <div className="form-field">
                <label>Full Name *</label>
                <input value={form.name} onChange={e => setForm(f => ({ ...f, name: e.target.value }))} placeholder="e.g. Jane Smith" />
              </div>
              <div className="form-field">
                <label>Jersey #</label>
                <input value={form.number} onChange={e => setForm(f => ({ ...f, number: e.target.value }))} placeholder="e.g. 14" />
              </div>
            </div>

            <div className="form-grid" style={{ marginBottom: 14 }}>
              <div className="form-field">
                <label>Position</label>
                <select value={form.position} onChange={e => setForm(f => ({ ...f, position: e.target.value, is_center: e.target.value !== 'F' ? false : f.is_center }))}>
                  {POSITIONS.map(p => <option key={p} value={p}>{p === 'F' ? 'Forward' : p === 'D' ? 'Defense' : 'Goalie'}</option>)}
                </select>
              </div>
              <div className="form-field" style={{ justifyContent: 'flex-end' }}>
                <label>Flags</label>
                <div className="toggle-row" style={{ marginTop: 4 }}>
                  <input
                    type="checkbox"
                    id="is_center"
                    checked={form.is_center}
                    disabled={form.position !== 'F'}
                    onChange={e => setForm(f => ({ ...f, is_center: e.target.checked }))}
                  />
                  <label htmlFor="is_center" style={{ marginBottom: 0, fontSize: 12, textTransform: 'none', letterSpacing: 0, color: form.position !== 'F' ? 'var(--text-secondary)' : 'var(--text)' }}>
                    Center (faceoff stats apply)
                  </label>
                </div>
                <div className="toggle-row" style={{ marginTop: 8 }}>
                  <input
                    type="checkbox"
                    id="active"
                    checked={form.active}
                    onChange={e => setForm(f => ({ ...f, active: e.target.checked }))}
                  />
                  <label htmlFor="active" style={{ marginBottom: 0, fontSize: 12, textTransform: 'none', letterSpacing: 0 }}>
                    Active (on current roster)
                  </label>
                </div>
              </div>
            </div>

            <div className="modal-actions">
              <button className="btn btn-ghost" onClick={() => setShowModal(false)}>Cancel</button>
              <button className="btn btn-primary" onClick={handleSave} disabled={saving}>
                {saving ? 'Saving…' : editing ? 'Save Changes' : 'Add Player'}
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  )
}
