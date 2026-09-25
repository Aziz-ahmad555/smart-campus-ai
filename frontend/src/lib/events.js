import { LogIn, LogOut, Users, PersonStanding, CircleHelp } from 'lucide-react'

// How each recognition-pipeline event type is shown across the app.
export const EVENT_TYPES = {
  ENTRY: { label: 'Entry', tone: 'success', icon: LogIn },
  EXIT: { label: 'Exit', tone: 'neutral', icon: LogOut },
  CROWD_ALERT: { label: 'Crowd alert', tone: 'warning', icon: Users },
  FALL_DETECTED: { label: 'Possible fall', tone: 'danger', icon: PersonStanding },
}

export function eventType(type) {
  return EVENT_TYPES[type] || { label: type, tone: 'neutral', icon: CircleHelp }
}

export const isAlert = (e) => e.type === 'CROWD_ALERT' || e.type === 'FALL_DETECTED'
