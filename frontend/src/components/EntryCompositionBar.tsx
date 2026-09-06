import type { ZoneEntryStats } from '../types'


const COLORS = {
  pass: '#4a9eff',
  stick: '#f5a742',
  dump: '#8a8a9a',
}


export default function EntryCompositionBar({ data }: { data?: ZoneEntryStats }) {
  if (!data || data.total_entries === 0) return null
  const p = (data.pass_pct ?? 0) * 100
  const s = (data.stick_pct ?? 0) * 100
  const d = (data.dump_pct ?? 0) * 100
  return (
    <div style={{ marginTop: 16 }}>
      <h3 style={{ fontSize: 14, marginBottom: 8, color: 'var(--text-secondary)' }}>
        Zone Entry Composition ({data.total_entries} entries · {data.games} game{data.games !== 1 ? 's' : ''})
      </h3>
      <div style={{ display: 'flex', height: 32, borderRadius: 4, overflow: 'hidden', border: '1px solid var(--border, #333)' }}>
        <div style={{ width: `${p}%`, background: COLORS.pass, display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'white', fontSize: 12 }}>
          {p >= 8 && `${p.toFixed(0)}%`}
        </div>
        <div style={{ width: `${s}%`, background: COLORS.stick, display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'white', fontSize: 12 }}>
          {s >= 8 && `${s.toFixed(0)}%`}
        </div>
        <div style={{ width: `${d}%`, background: COLORS.dump, display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'white', fontSize: 12 }}>
          {d >= 8 && `${d.toFixed(0)}%`}
        </div>
      </div>
      <div style={{ display: 'flex', gap: 16, marginTop: 8, fontSize: 12 }}>
        <span><span style={{ display: 'inline-block', width: 12, height: 12, background: COLORS.pass, marginRight: 4, verticalAlign: 'middle' }} />Pass</span>
        <span><span style={{ display: 'inline-block', width: 12, height: 12, background: COLORS.stick, marginRight: 4, verticalAlign: 'middle' }} />Stick</span>
        <span><span style={{ display: 'inline-block', width: 12, height: 12, background: COLORS.dump, marginRight: 4, verticalAlign: 'middle' }} />Dump</span>
      </div>
    </div>
  )
}
