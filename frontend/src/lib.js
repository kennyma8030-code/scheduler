// Shared display helpers. Times travel as minutes since midnight.

export const DAY_NAMES = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']

// The colors students already associate with each campus.
export const CAMPUS_COLORS = {
  1: { bg: '#f0c4c8', label: 'College Ave' },   // red
  2: { bg: '#b8cce8', label: 'Busch' },          // blue
  3: { bg: '#f0e4a8', label: 'Livingston' },     // yellow
  4: { bg: '#bfd8c4', label: 'Cook/Douglass' },  // green
  5: { bg: '#d8c4f0', label: 'Downtown' },       // purple
}

export function campusColor(code) {
  return CAMPUS_COLORS[code]?.bg ?? '#d8d4ce'
}

export function campusLabel(code) {
  return CAMPUS_COLORS[code]?.label ?? (code === 'O' ? 'Online' : code || '—')
}

export function fmtTime(min) {
  const m = Math.round(min)
  const h = Math.floor(m / 60)
  const mm = m % 60
  const suffix = h >= 12 && h < 24 ? 'p' : 'a'
  const h12 = h % 12 === 0 ? 12 : h % 12
  return mm === 0 ? `${h12}${suffix}` : `${h12}:${String(mm).padStart(2, '0')}${suffix}`
}

export function fmtCredits(credits) {
  if (credits === null || credits === undefined) return '~'
  return Number.isInteger(credits) ? String(credits) : credits.toFixed(1)
}
