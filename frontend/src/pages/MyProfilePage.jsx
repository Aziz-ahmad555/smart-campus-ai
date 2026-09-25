import { useMemo } from 'react'
import { Clock, LogIn, LogOut, CalendarCheck } from 'lucide-react'
import AppShell from '../components/layout/AppShell'
import { Card, CardHeader } from '../components/ui/Card'
import { Badge } from '../components/ui/Badge'
import { Avatar, PageHeader, StatCard } from '../components/ui/Misc'
import { EmptyState, ErrorBanner, Skeleton } from '../components/ui/States'
import { eventType } from '../lib/events'
import { formatDate, formatTime, parseTime, timeAgo } from '../lib/format'
import { getUser } from '../lib/session'
import { useApi } from '../lib/useApi'

export default function MyProfilePage() {
  const user = getUser()
  const activity = useApi('/secure/my-events', { auth: true, interval: 15000, initial: { events: [], linked: true } })

  const events = useMemo(() => activity.data.events.slice().reverse(), [activity.data])
  const linked = activity.data.linked !== false
  const lastEntry = events.find((e) => e.type === 'ENTRY')
  const entries = events.filter((e) => e.type === 'ENTRY').length
  const exits = events.filter((e) => e.type === 'EXIT').length

  // Group the timeline by day.
  const days = useMemo(() => {
    const groups = []
    for (const e of events) {
      const day = formatDate(e.timestamp)
      if (!groups.length || groups[groups.length - 1].day !== day) groups.push({ day, items: [] })
      groups[groups.length - 1].items.push(e)
    }
    return groups
  }, [events])

  return (
    <AppShell>
      <PageHeader title="My profile" description="Your account and your own campus activity" />

      <Card className="mb-6 flex flex-col gap-5 p-6 sm:flex-row sm:items-center">
        <Avatar name={user?.full_name || user?.username} size="lg" />
        <div className="flex-1">
          <h2 className="text-lg font-semibold text-slate-900 dark:text-white">{user?.full_name || user?.username}</h2>
          <p className="text-sm text-slate-500 dark:text-slate-400">@{user?.username}</p>
        </div>
        <Badge tone="info" className="self-start sm:self-center">Student</Badge>
      </Card>

      <ErrorBanner message={activity.error} onRetry={activity.reload} className="mb-6" />
      {!activity.loading && !linked && (
        <div role="status" className="mb-6 rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900 dark:border-amber-500/30 dark:bg-amber-500/10 dark:text-amber-200">
          Your account isn&apos;t linked to a student record yet, so no activity can be shown. Ask an administrator to link it.
        </div>
      )}

      <div className="mb-6 grid grid-cols-1 gap-4 sm:grid-cols-3">
        <StatCard
          label="Last seen"
          value={lastEntry ? formatTime(lastEntry.timestamp) : '—'}
          hint={lastEntry ? timeAgo(lastEntry.timestamp) : 'No entries recorded yet'}
          icon={CalendarCheck}
          tone="blue"
          loading={activity.loading}
        />
        <StatCard label="Entries" value={entries} icon={LogIn} tone="emerald" loading={activity.loading} />
        <StatCard label="Exits" value={exits} icon={LogOut} tone="slate" loading={activity.loading} />
      </div>

      <Card>
        <CardHeader icon={Clock} title="My activity" description="When the recognition system saw you enter or leave" />
        <div className="px-5 py-4">
          {activity.loading && <div className="space-y-3">{[0, 1, 2].map((i) => <Skeleton key={i} className="h-10" />)}</div>}
          {!activity.loading && !activity.error && events.length === 0 && (
            <EmptyState icon={Clock} title="No activity yet" description="Your entries and exits appear here once you're recognized on campus." />
          )}
          {days.map((group) => (
            <div key={group.day} className="mb-5 last:mb-0">
              <p className="mb-2 text-xs font-semibold uppercase tracking-wider text-slate-400 dark:text-slate-500">{group.day}</p>
              <ol className="relative ml-2 border-l border-slate-200 dark:border-slate-800">
                {group.items.map((e, i) => {
                  const t = eventType(e.type)
                  return (
                    <li key={`${e.timestamp}-${i}`} className="relative flex items-center gap-3 py-2 pl-6">
                      <span
                        className={`absolute -left-[5px] h-2.5 w-2.5 rounded-full ring-4 ring-white dark:ring-slate-900 ${
                          e.type === 'ENTRY' ? 'bg-emerald-500' : 'bg-slate-400'
                        }`}
                        aria-hidden="true"
                      />
                      <Badge tone={t.tone} icon={t.icon}>{t.label}</Badge>
                      <time dateTime={e.timestamp} className="text-sm tabular-nums text-slate-600 dark:text-slate-300">
                        {formatTime(parseTime(e.timestamp))}
                      </time>
                    </li>
                  )
                })}
              </ol>
            </div>
          ))}
        </div>
      </Card>
    </AppShell>
  )
}
