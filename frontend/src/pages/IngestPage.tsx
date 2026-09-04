import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { getGames, uploadIngest } from '../api/client'
import type { Game } from '../types'

export default function IngestPage() {
  const navigate = useNavigate()
  const [games, setGames] = useState<Game[]>([])
  const [gameId, setGameId] = useState<number | null>(null)
  const [file, setFile] = useState<File | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    getGames().then(setGames).catch((e) => setError(String(e)))
  }, [])

  async function submit(e: React.FormEvent) {
    e.preventDefault()
    if (!file || gameId === null) {
      setError('Pick a game and a PDF file.')
      return
    }
    setBusy(true)
    setError(null)
    try {
      const { ingest_run_id } = await uploadIngest(file, gameId)
      navigate(`/ingest/${ingest_run_id}`)
    } catch (err) {
      setError(String(err))
    } finally {
      setBusy(false)
    }
  }

  return (
    <div style={{ padding: 24, maxWidth: 640 }}>
      <h1>Ingest InStat Match Report</h1>
      <p style={{ color: 'var(--text-secondary)' }}>
        Upload an InStat match-report PDF for a game. The system parses it,
        then shows you the extracted values for review before committing.
      </p>
      <form onSubmit={submit} style={{ display: 'grid', gap: 16, marginTop: 16 }}>
        <label>
          Game:
          <select
            value={gameId ?? ''}
            onChange={(e) => setGameId(e.target.value ? Number(e.target.value) : null)}
            style={{ marginLeft: 8, padding: 4 }}
          >
            <option value="">— pick a game —</option>
            {games.map((g) => (
              <option key={g.id} value={g.id}>
                {g.date} vs. {g.opponent} ({g.is_home ? 'H' : 'A'})
              </option>
            ))}
          </select>
        </label>
        <label>
          PDF:
          <input
            type="file"
            accept="application/pdf"
            onChange={(e) => setFile(e.target.files?.[0] ?? null)}
            style={{ marginLeft: 8 }}
          />
        </label>
        <button type="submit" disabled={busy || !file || gameId === null}>
          {busy ? 'Uploading & parsing…' : 'Upload and parse'}
        </button>
        {error && (
          <div style={{ color: 'var(--color-red, #d63030)' }}>{error}</div>
        )}
      </form>
    </div>
  )
}
