import type { StatComparison } from '../types'

interface Props {
  label: string
  comparison: StatComparison
  unit?: 'pct' | 'per60' | 'min' | 'sec' | 'count'
}

const DOT_COLOR = {
  green:   '#7dbf88',
  yellow:  '#c8a84b',
  red:     '#c07272',
  neutral: '#6f7784',
}

function fmtVal(v: number | null, unit: Props['unit']): string {
  if (v === null || v === undefined) return '—'
  if (unit === 'pct')    return (v * 100).toFixed(1) + '%'
  if (unit === 'per60')  return v.toFixed(2)
  if (unit === 'min')    return v.toFixed(1) + ' min'
  if (unit === 'sec')    return v.toFixed(0) + ' s'
  return v.toFixed(0)
}

function fmtDelta(v: number | null, unit: Props['unit']): string {
  if (v === null || v === undefined) return '—'
  const prefix = v >= 0 ? '+' : ''
  if (unit === 'pct')    return prefix + (v * 100).toFixed(1) + '%'
  if (unit === 'per60')  return prefix + v.toFixed(2)
  return prefix + v.toFixed(1)
}

export default function ComparisonRow({ label, comparison, unit = 'per60' }: Props) {
  return (
    <div style={{ display: 'grid', gridTemplateColumns: '1fr auto auto auto auto', gap: 12, alignItems: 'center', padding: '8px 0', borderBottom: '1px solid var(--border)' }}>
      <div style={{ fontSize: 12, color: 'var(--text-secondary)', textTransform: 'uppercase', letterSpacing: '0.06em' }}>
        {label}
      </div>
      <div style={{ fontSize: 15, fontWeight: 700, color: 'var(--text)', minWidth: 70, textAlign: 'right' }}>
        {fmtVal(comparison.value, unit)}
      </div>
      <div style={{ fontSize: 11, color: 'var(--text-secondary)', minWidth: 90, textAlign: 'right' }}>
        vs team: <span style={{ color: 'var(--text)' }}>{fmtDelta(comparison.team_delta, unit)}</span>
      </div>
      <div style={{ fontSize: 11, color: 'var(--text-secondary)', minWidth: 100, textAlign: 'right' }}>
        vs {comparison.cohort}: <span style={{ color: 'var(--text)' }}>{fmtDelta(comparison.position_delta, unit)}</span>
      </div>
      <div style={{ width: 12, height: 12, borderRadius: 6, background: DOT_COLOR[comparison.indicator] }} />
    </div>
  )
}
