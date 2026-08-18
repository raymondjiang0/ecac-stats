import type { PlayerFlag } from '../types'

interface Props {
  flag: PlayerFlag
}

const STYLE_FOR_LABEL: Record<string, { bg: string; border: string; text: string }> = {
  'reduced role':  { bg: 'rgba(200, 100, 100, 0.12)', border: 'rgba(200, 100, 100, 0.5)', text: '#c07272' },
  'expanded role': { bg: 'rgba(120, 160, 200, 0.12)', border: 'rgba(120, 160, 200, 0.5)', text: '#7ba1c8' },
}

export default function GameFlagBadge({ flag }: Props) {
  const s = STYLE_FOR_LABEL[flag.label] ?? { bg: 'transparent', border: 'var(--border)', text: 'var(--text-secondary)' }
  return (
    <span style={{
      fontSize: 9, fontWeight: 700, letterSpacing: '0.08em', textTransform: 'uppercase',
      color: s.text, background: s.bg, border: `1px solid ${s.border}`,
      borderRadius: 4, padding: '2px 6px', marginLeft: 8,
    }}>
      {flag.label}
    </span>
  )
}
