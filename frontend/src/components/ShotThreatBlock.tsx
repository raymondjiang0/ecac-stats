import type { ShotThreatStats, ScenarioCell } from '../types'


function fmtCell(c: ScenarioCell): string {
  return `${c.shots}/${c.on_goal}`
}


function fmtPct(v: number | null): string {
  return v === null ? '—' : `${(v * 100).toFixed(0)}%`
}


function fmtRate(v: number | null | undefined): string {
  return v == null ? '—' : v.toFixed(1)
}


function StatSubBlock({ title, entries }: {
  title: string
  entries: [string, ScenarioCell, string?][]  // label, cell, optional extra column
}) {
  return (
    <div style={{ marginTop: 12 }}>
      <div style={{ fontSize: 11, color: 'var(--text-secondary)', marginBottom: 4, letterSpacing: '0.05em' }}>
        {title.toUpperCase()}
      </div>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(120px, 1fr))', gap: 6 }}>
        {entries.map(([label, cell, extra]) => (
          <div key={label} style={{
            padding: 8,
            border: '1px solid var(--border, #333)',
            borderRadius: 3,
            fontSize: 12,
          }}>
            <div style={{ color: 'var(--text-secondary)', fontSize: 10, marginBottom: 2 }}>
              {label}
            </div>
            <div style={{ fontWeight: 600 }}>{fmtCell(cell)}</div>
            {extra && (
              <div style={{ color: 'var(--text-secondary)', fontSize: 10 }}>{extra}</div>
            )}
          </div>
        ))}
      </div>
    </div>
  )
}


export default function ShotThreatBlock({ data }: { data?: ShotThreatStats }) {
  if (!data || data.games === 0) return null

  const strengthEntries: [string, ScenarioCell, string][] = [
    ['5v5', data.by_strength['5v5'], `${fmtRate(data.by_strength['5v5'].shots_per_60)} S/60`],
    ['PP', data.by_strength.pp, `${fmtRate(data.by_strength.pp.shots_per_60)} S/60`],
    ['SH', data.by_strength.sh, `${fmtRate(data.by_strength.sh.shots_per_60)} S/60`],
  ]

  const contextEntries: [string, ScenarioCell, string][] = [
    ['Positional', data.by_context.positional, fmtPct(data.by_context.positional.on_goal_pct)],
    ['Counter (rush)', data.by_context.counter, fmtPct(data.by_context.counter.on_goal_pct)],
  ]

  const locationEntries: [string, ScenarioCell, string][] = [
    ['Slot', data.by_location.slot, fmtPct(data.by_location.slot.on_goal_pct)],
    ['Center', data.by_location.center, fmtPct(data.by_location.center.on_goal_pct)],
    ['R Flank', data.by_location.right_flank, fmtPct(data.by_location.right_flank.on_goal_pct)],
    ['L Flank', data.by_location.left_flank, fmtPct(data.by_location.left_flank.on_goal_pct)],
    ['BL R', data.by_location.blue_line_right, fmtPct(data.by_location.blue_line_right.on_goal_pct)],
    ['BL C', data.by_location.blue_line_center, fmtPct(data.by_location.blue_line_center.on_goal_pct)],
    ['BL L', data.by_location.blue_line_left, fmtPct(data.by_location.blue_line_left.on_goal_pct)],
  ]

  const typeEntries: [string, ScenarioCell, string][] = [
    ['Slap', data.by_type.slapshot, fmtPct(data.by_type.slapshot.on_goal_pct)],
    ['Wrist', data.by_type.wristshot, fmtPct(data.by_type.wristshot.on_goal_pct)],
  ]

  return (
    <div style={{ marginTop: 16 }}>
      <h3 style={{ fontSize: 14, marginBottom: 8, color: 'var(--text-secondary)' }}>
        Shot Threat by Scenario ({data.totals.shots} shots · {data.totals.goals} G · {data.games} game{data.games !== 1 ? 's' : ''})
      </h3>
      <StatSubBlock title="Strength" entries={strengthEntries} />
      <StatSubBlock title="Location" entries={locationEntries} />
      <StatSubBlock title="Context" entries={contextEntries} />
      <StatSubBlock title="Type" entries={typeEntries} />
    </div>
  )
}
