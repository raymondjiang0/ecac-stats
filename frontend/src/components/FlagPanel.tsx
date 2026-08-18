import type { PlayerFlag } from '../types'

interface Props {
  flags: PlayerFlag[]
  onClickFlag?: (flag: PlayerFlag) => void
}

const COLOR_FOR_DIRECTION = {
  up:   { bg: 'rgba(120, 200, 130, 0.12)', border: 'rgba(120, 200, 130, 0.5)', text: '#7dbf88' },
  down: { bg: 'rgba(200, 100, 100, 0.12)', border: 'rgba(200, 100, 100, 0.5)', text: '#c07272' },
}

export default function FlagPanel({ flags, onClickFlag }: Props) {
  if (!flags || flags.length === 0) {
    return (
      <div style={{ fontSize: 12, color: 'var(--text-secondary)', fontStyle: 'italic', marginBottom: 20 }}>
        No flags this window.
      </div>
    )
  }
  return (
    <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap', marginBottom: 20 }}>
      <div style={{ fontSize: 10, fontWeight: 700, letterSpacing: '0.12em', textTransform: 'uppercase', color: 'var(--text-secondary)', alignSelf: 'center' }}>
        Flags this window:
      </div>
      {flags.map((f, i) => {
        const colors = COLOR_FOR_DIRECTION[f.direction] ?? COLOR_FOR_DIRECTION.up
        const arrow = f.direction === 'up' ? '⬆' : '⬇'
        return (
          <button
            key={i}
            onClick={() => onClickFlag?.(f)}
            style={{
              fontSize: 11,
              fontWeight: 600,
              color: colors.text,
              background: colors.bg,
              border: `1px solid ${colors.border}`,
              borderRadius: 12,
              padding: '4px 10px',
              cursor: onClickFlag ? 'pointer' : 'default',
              display: 'flex',
              alignItems: 'center',
              gap: 6,
            }}
          >
            <span>{arrow}</span>
            <span>{f.label}</span>
          </button>
        )
      })}
    </div>
  )
}
