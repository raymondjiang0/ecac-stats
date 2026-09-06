import type { ContestedPuckStats } from '../types'


function fmtPct(v: number | null): string {
  if (v === null) return 'N/A'
  return `${(v * 100).toFixed(1)}%`
}


export default function PuckBattleBlock({ data }: { data?: ContestedPuckStats }) {
  if (!data || data.games === 0) return null
  const cells = [
    { label: 'Overall', val: data.overall_pct },
    { label: 'DZ', val: data.dz_pct },
    { label: 'OZ', val: data.oz_pct },
    { label: 'NZ', val: data.nz_pct },
  ]
  return (
    <div style={{ marginTop: 16 }}>
      <h3 style={{ fontSize: 14, marginBottom: 8, color: 'var(--text-secondary)' }}>
        Puck Battles ({data.games} game{data.games !== 1 ? 's' : ''})
      </h3>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 8 }}>
        {cells.map(c => (
          <div key={c.label} style={{
            padding: 12,
            border: '1px solid var(--border, #333)',
            borderRadius: 4,
            textAlign: 'center',
          }}>
            <div style={{ fontSize: 11, color: 'var(--text-secondary)', marginBottom: 4 }}>
              {c.label}
            </div>
            <div style={{ fontSize: 18, fontWeight: 600 }}>
              {fmtPct(c.val)}
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}
