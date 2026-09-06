import type { ImpactScoreStats } from '../types'


function scoreColor(score: number | null): string {
  if (score === null) return 'var(--text-secondary)'
  if (score >= 1) return 'var(--color-green, #4ecb71)'
  if (score >= 0) return 'var(--text-primary, #eaeaf0)'
  if (score >= -1) return 'var(--color-orange, #f5a742)'
  return 'var(--color-red, #d63030)'
}


function averageComponents(perGame: ImpactScoreStats['per_game']): Record<string, number | null> {
  const totals: Record<string, { sum: number; count: number }> = {}
  for (const g of perGame) {
    for (const [k, v] of Object.entries(g.components)) {
      if (typeof v !== 'number') continue
      const entry = totals[k] ?? { sum: 0, count: 0 }
      entry.sum += v
      entry.count += 1
      totals[k] = entry
    }
  }
  const out: Record<string, number | null> = {}
  for (const [k, { sum, count }] of Object.entries(totals)) {
    out[k] = count > 0 ? sum / count : null
  }
  return out
}


const LABELS: Record<string, string> = {
  z_xg: 'xG diff (on-ice)',
  z_terr: 'Territory (CF%)',
  z_battle: 'Puck battle W%',
  z_entry: 'Controlled entry %',
}


export default function ImpactScoreCard({ data }: { data?: ImpactScoreStats }) {
  if (!data) return null
  const scoreDisplay = data.score === null ? 'N/A' : data.score.toFixed(2)
  const componentAvgs = averageComponents(data.per_game)
  const tooltip = Object.entries(componentAvgs)
    .map(([k, v]) => `${LABELS[k] ?? k}: ${v === null ? 'N/A' : v.toFixed(2)}σ`)
    .join('\n')

  return (
    <div style={{ marginTop: 16 }}>
      <h3 style={{ fontSize: 14, marginBottom: 8, color: 'var(--text-secondary)' }}>
        Impact Score
      </h3>
      <div
        title={tooltip || 'No component data'}
        style={{
          padding: 24,
          border: '1px solid var(--border, #333)',
          borderRadius: 4,
          textAlign: 'center',
          cursor: tooltip ? 'help' : 'default',
        }}
      >
        <div style={{ fontSize: 40, fontWeight: 700, color: scoreColor(data.score) }}>
          {scoreDisplay}
        </div>
        <div style={{ fontSize: 11, color: 'var(--text-secondary)', marginTop: 4 }}>
          {data.games} game{data.games !== 1 ? 's' : ''} · {data.components_used.length} component{data.components_used.length !== 1 ? 's' : ''}
          {data.clamped && ' · clamped'}
        </div>
      </div>
    </div>
  )
}
