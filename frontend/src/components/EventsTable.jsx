import { LogIn, LogOut, AlertTriangle, HelpCircle } from 'lucide-react'

function EventBadge({ type }) {
  const config = {
    ENTRY: { icon: LogIn, bg: 'bg-emerald-100 dark:bg-emerald-900/30', text: 'text-emerald-700 dark:text-emerald-400', label: 'Entry' },
    EXIT: { icon: LogOut, bg: 'bg-rose-100 dark:bg-rose-900/30', text: 'text-rose-700 dark:text-rose-400', label: 'Exit' },
    CROWD_ALERT: { icon: AlertTriangle, bg: 'bg-amber-100 dark:bg-amber-900/30', text: 'text-amber-700 dark:text-amber-400', label: 'Crowd Alert' },
  }
  const c = config[type] || { icon: HelpCircle, bg: 'bg-slate-100', text: 'text-slate-700', label: type }
  const Icon = c.icon
  const badgeClass = 'inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-semibold ' + c.bg + ' ' + c.text

  return (
    <span className={badgeClass}>
      <Icon size={12} />
      {c.label}
    </span>
  )
}

function EventsTable({ events }) {
  return (
    <div className="bg-white dark:bg-slate-800 rounded-xl border border-slate-200 dark:border-slate-700 shadow-sm overflow-hidden">
      <div className="p-5 border-b border-slate-200 dark:border-slate-700">
        <h3 className="font-semibold text-slate-900 dark:text-white">Recognition Event Log</h3>
        <p className="text-xs text-slate-500 dark:text-slate-400 mt-0.5">Live feed from inference pipeline</p>
      </div>
      <div className="overflow-x-auto max-h-96 overflow-y-auto">
        <table className="w-full text-sm">
          <thead className="bg-slate-50 dark:bg-slate-900/50 sticky top-0">
            <tr className="text-left text-xs text-slate-500 dark:text-slate-400 uppercase tracking-wide">
              <th className="px-5 py-3 font-medium">Event</th>
              <th className="px-5 py-3 font-medium">Track ID</th>
              <th className="px-5 py-3 font-medium">Identity</th>
              <th className="px-5 py-3 font-medium">Timestamp</th>
            </tr>
          </thead>
          <tbody>
            {events.length === 0 && (
              <tr>
                <td colSpan="4" className="px-5 py-8 text-center text-slate-400 text-sm">
                  Awaiting detections from inference pipeline...
                </td>
              </tr>
            )}
            {events.map((event, index) => (
              <tr key={index} className="border-t border-slate-100 dark:border-slate-700/50 hover:bg-slate-50 dark:hover:bg-slate-700/30">
                <td className="px-5 py-3"><EventBadge type={event.type} /></td>
                <td className="px-5 py-3 text-slate-600 dark:text-slate-300 font-mono text-xs">
                  {event.track_id ?? '—'}
                </td>
                <td className="px-5 py-3 text-slate-900 dark:text-slate-100 font-medium">{event.label}</td>
                <td className="px-5 py-3 text-slate-500 dark:text-slate-400 text-xs">{event.timestamp}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}

export default EventsTable
