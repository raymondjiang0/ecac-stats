interface Props {
  valueMinutes: string   // stored as decimal-minutes string in form state
  onChange: (decimalMinutes: string) => void
  placeholder?: string
}

function toBoxes(decMinStr: string): { m: string; s: string } {
  const dec = parseFloat(decMinStr)
  if (isNaN(dec) || decMinStr.trim() === '') return { m: '', s: '' }
  const m = Math.floor(dec)
  const s = Math.round((dec - m) * 60)
  return { m: String(m), s: s === 0 ? '0' : String(s) }
}

function toDecimal(m: string, s: string): string {
  const mins = parseInt(m, 10)
  const secs = parseInt(s, 10)
  if (isNaN(mins) && isNaN(secs)) return ''
  const totalMins = (isNaN(mins) ? 0 : mins) + (isNaN(secs) ? 0 : secs) / 60
  return String(totalMins)
}

export default function ToiInput({ valueMinutes, onChange, placeholder = '0' }: Props) {
  const { m, s } = toBoxes(valueMinutes)

  function handleMin(val: string) {
    onChange(toDecimal(val, s))
  }

  function handleSec(val: string) {
    // clamp seconds 0-59
    const n = parseInt(val, 10)
    const clamped = isNaN(n) ? '' : String(Math.min(59, Math.max(0, n)))
    onChange(toDecimal(m, clamped))
  }

  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
      <input
        type="number"
        value={m}
        onChange={e => handleMin(e.target.value)}
        placeholder={placeholder}
        min="0"
        style={{ width: '60%', textAlign: 'right' }}
      />
      <span style={{ color: 'var(--text-secondary)', fontWeight: 700, fontSize: 14, flexShrink: 0 }}>:</span>
      <input
        type="number"
        value={s}
        onChange={e => handleSec(e.target.value)}
        placeholder="00"
        min="0"
        max="59"
        style={{ width: '40%', textAlign: 'center' }}
      />
    </div>
  )
}
