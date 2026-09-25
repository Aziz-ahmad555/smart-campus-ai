import { LogIn, LogOut, Users, PersonStanding, CircleHelp, ScanFace } from 'lucide-react'

// How each recognition-pipeline event type is shown across the app.
export const EVENT_TYPES = {
  ENTRY: { label: 'Entry', tone: 'success', icon: LogIn },
  EXIT: { label: 'Exit', tone: 'neutral', icon: LogOut },
  CROWD_ALERT: { label: 'Crowd alert', tone: 'warning', icon: Users },
  FALL_DETECTED: { label: 'Possible fall', tone: 'danger', icon: PersonStanding },
  IDENTIFYING: { label: 'Identifying…', tone: 'info', icon: ScanFace },
}

export function eventType(type) {
  return EVENT_TYPES[type] || { label: type, tone: 'neutral', icon: CircleHelp }
}

export const isAlert = (e) => e.type === 'CROWD_ALERT' || e.type === 'FALL_DETECTED'

// People the pipeline is still identifying, by track id. The backend sends a
// live-only IDENTIFYING notice when someone appears and writes one ENTRY once
// they're identified (or Unknown after the re-checks, or when they leave), so
// an ENTRY/EXIT for the track ends it. Notices older than IDENTIFYING_TTL_MS
// are dropped in case the ENTRY was missed (e.g. while reconnecting).
export const IDENTIFYING_TTL_MS = 60000

export function trackIdentifying(current, event, nowMs = Date.now()) {
  const next = {}
  for (const [id, entry] of Object.entries(current)) {
    if (nowMs - entry.seenAt < IDENTIFYING_TTL_MS) next[id] = entry
  }
  if (event?.track_id != null) {
    if (event.type === 'IDENTIFYING') next[event.track_id] = { ...event, seenAt: nowMs }
    else if (event.type === 'ENTRY' || event.type === 'EXIT') delete next[event.track_id]
  }
  return next
}
