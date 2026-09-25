import { useMemo } from 'react'
import { Users, LogIn, ScanFace, AlertTriangle } from 'lucide-react'
import AppShell from '../components/layout/AppShell'
import TrafficChart from '../components/dashboard/TrafficChart'
import LiveFeed from '../components/dashboard/LiveFeed'
import EventsTable from '../components/dashboard/EventsTable'
import { Badge } from '../components/ui/Badge'
import { PageHeader, StatCard } from '../components/ui/Misc'
import { ErrorBanner } from '../components/ui/States'
import { isAlert } from '../lib/events'
import { useLiveEvents } from '../lib/useLiveEvents'

const CONNECTION = {
  live: { tone: 'success', label: 'Live' },
  connecting: { tone: 'neutral', label: 'Connecting…' },
  offline: { tone: 'danger', label: 'Reconnecting…' },
}

export default function DashboardPage() {
  const { events, status, error, loadOlder, hasOlder, loadingOlder } = useLiveEvents()

  const stats = useMemo(() => {
    const inside = new Set()
    for (const e of events.slice().reverse()) {
      if (e.type === 'ENTRY') inside.add(e.track_id)
      if (e.type === 'EXIT') inside.delete(e.track_id)
    }
    const known = new Set(events.filter((e) => e.type === 'ENTRY' && e.label !== 'Unknown').map((e) => e.label))
    return {
      occupancy: inside.size,
      entries: events.filter((e) => e.type === 'ENTRY').length,
      identities: known.size,
      alerts: events.filter(isAlert).length,
    }
  }, [events])

  // A failed initial load means the backend is down, even while the socket is still trying.
  const conn = error && status !== 'live' ? { tone: 'danger', label: 'Offline' } : CONNECTION[status]

  return (
    <AppShell>
      <PageHeader
        title="Live dashboard"
        description="Detection, recognition and access tracking in real time"
        actions={<Badge tone={conn.tone} dot className="px-2.5 py-1">{conn.label}</Badge>}
      />

      <ErrorBanner message={error} className="mb-6" />

      <div className="mb-6 grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <StatCard label="People in view" value={stats.occupancy} hint="Tracked now, based on entries and exits" icon={Users} tone="blue" />
        <StatCard label="Entries" value={stats.entries} hint="In the loaded event history" icon={LogIn} tone="emerald" />
        <StatCard label="Identities recognized" value={stats.identities} hint="Distinct known people" icon={ScanFace} tone="violet" />
        <StatCard
          label="Alerts"
          value={stats.alerts}
          hint="Crowd and possible-fall events"
          icon={AlertTriangle}
          tone={stats.alerts ? 'amber' : 'slate'}
        />
      </div>

      <div className="mb-6 grid grid-cols-1 gap-6 xl:grid-cols-2">
        <LiveFeed />
        <TrafficChart events={events} />
      </div>

      <EventsTable
        events={events}
        loading={status === 'connecting' && events.length === 0}
        onLoadOlder={loadOlder}
        hasOlder={hasOlder}
        loadingOlder={loadingOlder}
      />
    </AppShell>
  )
}
