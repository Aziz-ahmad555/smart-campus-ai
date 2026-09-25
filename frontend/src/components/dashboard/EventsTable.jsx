import { useEffect, useMemo, useState } from 'react'
import { ListChecks, Search, Radio } from 'lucide-react'
import { Card, CardHeader } from '../ui/Card'
import { Badge } from '../ui/Badge'
import { SearchInput } from '../ui/Field'
import { Tabs } from '../ui/Misc'
import { EmptyState } from '../ui/States'
import { Table, Row, Cell, EmptyRow } from '../ui/Table'
import { LoadOlder } from '../ui/LoadOlder'
import { eventType, isAlert } from '../../lib/events'
import { formatTime, timeAgo } from '../../lib/format'

export function EventBadge({ type }) {
  const t = eventType(type)
  return <Badge tone={t.tone} icon={t.icon}>{t.label}</Badge>
}

const FILTERS = {
  all: () => true,
  ENTRY: (e) => e.type === 'ENTRY',
  EXIT: (e) => e.type === 'EXIT',
  alerts: isAlert,
}

export default function EventsTable({ events, loading, onLoadOlder, hasOlder = false, loadingOlder = false }) {
  const [filter, setFilter] = useState('all')
  const [query, setQuery] = useState('')
  const [now, setNow] = useState(new Date())

  useEffect(() => {
    const id = setInterval(() => setNow(new Date()), 15000)
    return () => clearInterval(id)
  }, [])

  const counts = useMemo(
    () => Object.fromEntries(Object.entries(FILTERS).map(([k, fn]) => [k, events.filter(fn).length])),
    [events],
  )
  const q = query.trim().toLowerCase()
  const shown = events.filter(FILTERS[filter]).filter((e) => !q || (e.label || '').toLowerCase().includes(q))

  return (
    <Card>
      <CardHeader
        icon={ListChecks}
        title="Event log"
        description="Entries, exits and alerts from the recognition pipeline, newest first"
      />
      <div className="flex flex-col gap-3 border-b border-slate-100 px-5 py-3 sm:flex-row sm:items-center sm:justify-between dark:border-slate-800">
        <Tabs
          label="Filter events"
          value={filter}
          onChange={setFilter}
          options={[
            { value: 'all', label: 'All', count: counts.all },
            { value: 'ENTRY', label: 'Entries', count: counts.ENTRY },
            { value: 'EXIT', label: 'Exits', count: counts.EXIT },
            { value: 'alerts', label: 'Alerts', count: counts.alerts },
          ]}
        />
        <SearchInput value={query} onChange={setQuery} placeholder="Search by name or roll number" icon={Search} className="sm:w-72" />
      </div>
      <div className="max-h-[28rem] overflow-y-auto">
        <Table
          columns={[
            { label: 'Event' },
            { label: 'Identity' },
            { label: 'Track', className: 'hidden sm:table-cell' },
            { label: 'Time', className: 'text-right' },
          ]}
        >
          {!loading && shown.length === 0 && (
            <EmptyRow colSpan={4}>
              <EmptyState
                icon={Radio}
                title={events.length ? 'No matching events' : 'Waiting for detections'}
                description={events.length ? 'Try another filter or search.' : 'Events appear here the moment the pipeline sees someone.'}
              />
            </EmptyRow>
          )}
          {shown.map((e, i) => (
            <Row key={e.id ?? `live-${e.timestamp}-${e.type}-${e.track_id}-${i}`}>
              <Cell><EventBadge type={e.type} /></Cell>
              <Cell className={e.label === 'Unknown' ? 'italic text-slate-500 dark:text-slate-400' : 'font-medium text-slate-900 dark:text-white'}>
                {e.label === 'Unknown' ? 'Unknown person' : e.label}
              </Cell>
              <Cell className="hidden font-mono text-xs text-slate-500 sm:table-cell dark:text-slate-400">
                {e.track_id != null ? `#${e.track_id}` : '—'}
              </Cell>
              <Cell className="text-right">
                <time dateTime={e.timestamp} title={e.timestamp} className="text-xs tabular-nums text-slate-500 dark:text-slate-400">
                  <span className="text-slate-700 dark:text-slate-300">{formatTime(e.timestamp)}</span>
                  <span className="ml-2 hidden md:inline">{timeAgo(e.timestamp, now)}</span>
                </time>
              </Cell>
            </Row>
          ))}
        </Table>
        <LoadOlder hasOlder={hasOlder} loading={loadingOlder} onClick={onLoadOlder} />
      </div>
    </Card>
  )
}
