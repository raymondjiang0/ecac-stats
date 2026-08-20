import SmallSampleBadge from './SmallSampleBadge'
import type { StatAvailability } from '../types'

interface Props {
  label: string
  sublabel?: string
  primary: string
  secondary?: string
  context?: string
  vsTeam?: { diff: number; teamVal: string } | null
  smallSample?: boolean
  gamesPlayed?: number
  trend?: (number | null)[]
  trendLabel?: string
  availability?: StatAvailability
}

function Sparkline({ values }: { values: (number | null)[] }) {
  const valid = values.filter((v): v is number => v !== null)
  if (valid.length === 0) return null
  const max = Math.max(...valid)
  const min = Math.min(...valid)
  const range = Math.max(max - min, 0.001)

  return (
    <div style={{ display: 'flex', alignItems: 'flex-end', gap: 2, height: 22, marginTop: 8 }}>
      {values.map((v, i) => (
        <div
          key={i}
          style={{
            flex: 1,
            background: v !== null ? 'var(--crimson)' : 'var(--border)',
            opacity: v !== null ? 0.65 : 1,
            borderRadius: '2px 2px 0 0',
            height: v !== null ? Math.max(((v - min) / range) * 18 + 2, 2) : 4,
            minWidth: 4,
          }}
          title={v !== null ? v.toFixed(3) : 'no data'}
        />
      ))}
    </div>
  )
}

export default function StatCard({
  label, sublabel, primary, secondary, context,
  vsTeam, smallSample, gamesPlayed = 0, trend, trendLabel, availability,
}: Props) {
  return (
    <div className="card" style={{ borderTop: '3px solid var(--crimson)', padding: '14px 16px' }}>
      <div style={{ fontSize: 10, fontWeight: 700, letterSpacing: '0.1em', textTransform: 'uppercase', color: 'var(--text-secondary)', marginBottom: 8 }}>
        {label}
      </div>

      <div style={{ display: 'flex', alignItems: 'baseline', gap: 8, marginBottom: 4 }}>
        {availability && availability.games === 0
          ? <span style={{ fontSize: 28, fontWeight: 700, color: 'var(--text-secondary)', fontStyle: 'italic', lineHeight: 1 }} title={`Source ${availability.sources.join(', ') || 'unavailable'} for this window`}>N/A</span>
          : <span style={{ fontSize: 28, fontWeight: 700, color: primary === '—' ? 'var(--text-secondary)' : 'var(--text)', lineHeight: 1, fontVariantNumeric: 'tabular-nums' }}>
              {primary}
            </span>
        }
        {secondary && (
          <span style={{ fontSize: 13, color: 'var(--text-secondary)', fontWeight: 500 }}>
            {secondary}
          </span>
        )}
      </div>

      {sublabel && (
        <div style={{ fontSize: 11, fontWeight: 600, color: 'var(--text)', marginBottom: 4 }}>
          {sublabel}
        </div>
      )}

      {context && (
        <div style={{ fontSize: 11, color: 'var(--text-secondary)', lineHeight: 1.4, marginTop: 4 }}>
          {context}
        </div>
      )}

      {vsTeam && (
        <div style={{ marginTop: 6 }}>
          <span
            className={`stat-pill ${vsTeam.diff > 0.005 ? 'positive' : vsTeam.diff < -0.005 ? 'negative' : 'neutral'}`}
          >
            {vsTeam.diff >= 0 ? '+' : ''}{(vsTeam.diff * 100).toFixed(1)}% vs team {vsTeam.teamVal}
          </span>
        </div>
      )}

      {trend && <Sparkline values={trend} />}

      {trendLabel && (
        <div style={{ fontSize: 10, color: 'var(--text-secondary)', marginTop: 4, fontStyle: 'italic' }}>
          {trendLabel}
        </div>
      )}

      {smallSample && (
        <div style={{ marginTop: 8 }}>
          <SmallSampleBadge n={gamesPlayed} />
        </div>
      )}
    </div>
  )
}
