import { useEffect, useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { getIngestRun, commitIngest, discardIngest } from '../api/client'
import type { IngestRun, IngestPreview, IngestTeamStats } from '../types'


export default function IngestReviewPage() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const [run, setRun] = useState<IngestRun | null>(null)
  const [preview, setPreview] = useState<IngestPreview | null>(null)
  const [loadError, setLoadError] = useState<string | null>(null)
  const [submitError, setSubmitError] = useState<string | null>(null)
  const [result, setResult] = useState<{ wrote: Record<string, number>; skipped: string[] } | null>(null)
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    if (!id) return
    getIngestRun(Number(id))
      .then((r) => {
        setRun(r)
        setPreview(r.parsed_json.templates)
      })
      .catch((e) => setLoadError(String(e)))
  }, [id])

  if (loadError) return <div style={{ padding: 24, color: 'var(--color-red)' }}>{loadError}</div>
  if (!run || !preview) return <div style={{ padding: 24 }}>Loading…</div>

  async function commit() {
    setBusy(true)
    setSubmitError(null)
    try {
      const r = await commitIngest(Number(id), { templates: preview!, warnings: run!.parsed_json.warnings })
      setResult(r)
    } catch (e) {
      setSubmitError(String(e))
    } finally {
      setBusy(false)
    }
  }

  async function discard() {
    if (!confirm('Discard this ingest? The uploaded PDF is preserved but no DB changes will be made.')) return
    setBusy(true)
    setSubmitError(null)
    try {
      await discardIngest(Number(id))
      navigate('/ingest')
    } catch (e) {
      setSubmitError(String(e))
    } finally {
      setBusy(false)
    }
  }

  if (result) {
    return (
      <div style={{ padding: 24 }}>
        <h1>Committed ✓</h1>
        <p>Rows written per template:</p>
        <ul>
          {Object.entries(result.wrote).map(([k, v]) => (
            <li key={k}>{k}: {v}</li>
          ))}
        </ul>
        {result.skipped.length > 0 && (
          <>
            <p style={{ marginTop: 16 }}>Skipped rows:</p>
            <ul>{result.skipped.map((s, i) => <li key={i}>{s}</li>)}</ul>
          </>
        )}
        <button onClick={() => navigate('/ingest')}>Back to ingest</button>
      </div>
    )
  }

  return (
    <div style={{ padding: 24, maxWidth: 1000 }}>
      <h1>Review ingest: {run.filename}</h1>
      <p style={{ color: 'var(--text-secondary)' }}>
        Status: {run.status} · Game #{run.game_id} · Uploaded {run.uploaded_at}
      </p>

      {run.parsed_json.warnings.length > 0 && (
        <div style={{ background: 'var(--warn-bg, #4a3a1e)', padding: 12, borderRadius: 4, marginBottom: 16 }}>
          <strong>Warnings:</strong>
          <ul>{run.parsed_json.warnings.map((w, i) => <li key={i}>{w}</li>)}</ul>
        </div>
      )}

      <TemplateSection title="Team stats" data={preview.instat_team_stats}
        onChange={(v) => setPreview({ ...preview, instat_team_stats: v })} />

      <PlayerRowsSection title="Players (main)" rows={preview.instat_players_main}
        onChange={(v) => setPreview({ ...preview, instat_players_main: v })} />

      <PlayerRowsSection title="Time distribution" rows={preview.instat_time_distribution}
        onChange={(v) => setPreview({ ...preview, instat_time_distribution: v })} />

      <PlayerRowsSection title="Challenges (puck battles)" rows={preview.instat_challenges}
        onChange={(v) => setPreview({ ...preview, instat_challenges: v })} />

      <MatrixSection title={`Hit matrix (${preview.instat_hit_matrix.length} pairs)`}
        rows={preview.instat_hit_matrix} kind="hits" />

      <MatrixSection title={`Pass matrix (${preview.instat_pass_matrix.length} pairs)`}
        rows={preview.instat_pass_matrix} kind="passes" />

      <div style={{ marginTop: 24, display: 'flex', gap: 12 }}>
        <button onClick={commit} disabled={busy}>
          {busy ? 'Committing…' : 'Commit to database'}
        </button>
        <button onClick={discard} disabled={busy} style={{ background: 'transparent' }}>
          Discard
        </button>
      </div>
      {submitError && <div style={{ color: 'var(--color-red)', marginTop: 8 }}>{submitError}</div>}
    </div>
  )
}


function TemplateSection({
  title, data, onChange,
}: { title: string; data: IngestTeamStats; onChange: (v: IngestTeamStats) => void }) {
  const [open, setOpen] = useState(true)
  return (
    <details open={open} onToggle={(e) => setOpen((e.target as HTMLDetailsElement).open)}
      style={{ border: '1px solid var(--border-color, #333)', borderRadius: 4, padding: 8, marginTop: 12 }}>
      <summary style={{ cursor: 'pointer', fontWeight: 600 }}>{title}</summary>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: 8, marginTop: 8 }}>
        {(Object.keys(data) as Array<keyof IngestTeamStats>).map((k) => (
          <label key={k} style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
            <span style={{ minWidth: 200 }}>{k}:</span>
            <input
              type="number"
              value={data[k] ?? ''}
              step="any"
              onChange={(e) => onChange({ ...data, [k]: e.target.value === '' ? null : Number(e.target.value) })}
              style={{ padding: 4, flex: 1 }}
            />
          </label>
        ))}
      </div>
    </details>
  )
}


function PlayerRowsSection({
  title, rows, onChange,
}: { title: string; rows: any[]; onChange: (v: any[]) => void }) {
  const [open, setOpen] = useState(false)
  if (rows.length === 0) return null
  const keys = Object.keys(rows[0])
  return (
    <details open={open} onToggle={(e) => setOpen((e.target as HTMLDetailsElement).open)}
      style={{ border: '1px solid var(--border-color, #333)', borderRadius: 4, padding: 8, marginTop: 12 }}>
      <summary style={{ cursor: 'pointer', fontWeight: 600 }}>{title} ({rows.length} players)</summary>
      <table style={{ marginTop: 8, width: '100%', borderCollapse: 'collapse' }}>
        <thead>
          <tr>{keys.map((k) => <th key={k} style={{ textAlign: 'left', padding: 4, borderBottom: '1px solid #333' }}>{k}</th>)}</tr>
        </thead>
        <tbody>
          {rows.map((r, i) => (
            <tr key={i}>
              {keys.map((k) => (
                <td key={k} style={{ padding: 2 }}>
                  <input
                    value={r[k] ?? ''}
                    onChange={(e) => {
                      const next = [...rows]
                      const val = e.target.value
                      next[i] = { ...r, [k]: val === '' ? null : (isNaN(Number(val)) ? val : Number(val)) }
                      onChange(next)
                    }}
                    style={{ width: '100%', padding: 2, border: '1px solid #444', background: 'transparent', color: 'inherit' }}
                  />
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </details>
  )
}


function MatrixSection({
  title, rows, kind,
}: { title: string; rows: any[]; kind: 'hits' | 'passes' }) {
  const [open, setOpen] = useState(false)
  if (rows.length === 0) return null
  return (
    <details open={open} onToggle={(e) => setOpen((e.target as HTMLDetailsElement).open)}
      style={{ border: '1px solid var(--border-color, #333)', borderRadius: 4, padding: 8, marginTop: 12 }}>
      <summary style={{ cursor: 'pointer', fontWeight: 600 }}>{title}</summary>
      <table style={{ marginTop: 8, borderCollapse: 'collapse', fontSize: 13 }}>
        <thead>
          <tr>
            <th style={{ padding: 4 }}>From</th>
            <th style={{ padding: 4 }}>To</th>
            {kind === 'hits' ? (
              <>
                <th style={{ padding: 4 }}>Delivered</th>
                <th style={{ padding: 4 }}>Received</th>
              </>
            ) : (
              <th style={{ padding: 4 }}>Count</th>
            )}
          </tr>
        </thead>
        <tbody>
          {rows.map((r, i) => (
            <tr key={i}>
              <td style={{ padding: 4 }}>#{r.from_jersey} {r.from_name}</td>
              <td style={{ padding: 4 }}>#{r.to_jersey} {r.to_name}</td>
              {kind === 'hits' ? (
                <>
                  <td style={{ padding: 4 }}>{r.delivered}</td>
                  <td style={{ padding: 4 }}>{r.received}</td>
                </>
              ) : (
                <td style={{ padding: 4 }}>{r.count}</td>
              )}
            </tr>
          ))}
        </tbody>
      </table>
      <p style={{ marginTop: 8, color: 'var(--text-secondary)', fontSize: 12 }}>
        Matrix rows are read-only in this view — edit players' main stats above if a jersey needs to change.
      </p>
    </details>
  )
}
