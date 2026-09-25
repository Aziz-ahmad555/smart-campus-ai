// Backend timestamps are local-time strings ("2026-08-31 16:34:00" or ISO).
export function parseTime(value) {
  if (!value) return null
  const d = value instanceof Date ? value : new Date(String(value).replace(' ', 'T'))
  return Number.isNaN(d.getTime()) ? null : d
}

export function formatTime(value) {
  const d = parseTime(value)
  return d ? d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' }) : '—'
}

export function formatDate(value) {
  const d = parseTime(value)
  return d ? d.toLocaleDateString([], { day: 'numeric', month: 'short', year: 'numeric' }) : '—'
}

export function formatDateTime(value) {
  const d = parseTime(value)
  return d ? d.toLocaleString([], { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' }) : '—'
}

export function timeAgo(value, now = new Date()) {
  const d = parseTime(value)
  if (!d) return '—'
  const secs = Math.round((now - d) / 1000)
  if (secs < 10) return 'just now'
  if (secs < 60) return `${secs}s ago`
  const mins = Math.floor(secs / 60)
  if (mins < 60) return `${mins} min ago`
  const hours = Math.floor(mins / 60)
  if (hours < 24) return `${hours} h ago`
  return formatDate(d)
}

export function initials(name) {
  return (name || '?')
    .replace(/\(.*\)/, '')
    .trim()
    .split(/\s+/)
    .slice(0, 2)
    .map((part) => part[0]?.toUpperCase() || '')
    .join('') || '?'
}
