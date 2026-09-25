import { useMemo } from 'react'
import { Users, LogIn, Clock, School } from 'lucide-react'
import AppShell from '../components/layout/AppShell'
import { EventBadge } from '../components/dashboard/EventsTable'
import { Card, CardHeader } from '../components/ui/Card'
import { Avatar, PageHeader, StatCard } from '../components/ui/Misc'
import { EmptyState, ErrorBanner, SkeletonRows } from '../components/ui/States'
import { Table, Row, Cell, EmptyRow } from '../components/ui/Table'
import { formatTime, parseTime } from '../lib/format'
import { getUser } from '../lib/session'
import { useApi } from '../lib/useApi'

export default function MyClassPage() {
  const user = getUser()
  // Roster and activity both come from the teacher's own session.
  const roster = useApi('/secure/my-class-roster', { auth: true, interval: 15000, initial: { class_name: null, students: [], events: [], linked: true } })
  const { class_name: className, students = [], events = [], linked = true } = roster.data

  const today = new Date().toDateString()
  const recent = useMemo(() => events.slice().reverse(), [events])
  const seenToday = useMemo(
    () => new Set(events.filter((e) => e.type === 'ENTRY' && parseTime(e.timestamp)?.toDateString() === today).map((e) => e.label)).size,
    [events, today],
  )

  return (
    <AppShell>
      <PageHeader
        title={className || 'My class'}
        description={`Welcome back${user?.full_name ? `, ${user.full_name}` : ''}. Your class roster and recent campus activity.`}
      />

      <ErrorBanner message={roster.error} onRetry={roster.reload} className="mb-6" />

      {!roster.loading && !roster.error && !className ? (
        <Card>
          {linked ? (
            <EmptyState icon={School} title="No class assigned yet" description="Ask an administrator to assign you to a class." />
          ) : (
            <EmptyState
              icon={School}
              title="Your account isn't linked to a staff record"
              description="Ask an administrator to link your account to your staff record so your class appears here."
            />
          )}
        </Card>
      ) : (
        <>
          <div className="mb-6 grid grid-cols-1 gap-4 sm:grid-cols-3">
            <StatCard label="Students" value={students.length} icon={Users} tone="blue" loading={roster.loading} />
            <StatCard label="Seen on campus today" value={seenToday} hint="Recognized at least once" icon={LogIn} tone="emerald" loading={roster.loading} />
            <StatCard label="Recent events" value={events.length} hint="Entries and exits for your class" icon={Clock} tone="violet" loading={roster.loading} />
          </div>

          <div className="grid grid-cols-1 gap-6 xl:grid-cols-5">
            <Card className="xl:col-span-2">
              <CardHeader icon={Users} title="Roster" description={`${students.length} student${students.length === 1 ? '' : 's'}`} />
              <Table columns={[{ label: 'Student' }, { label: 'Roll number', className: 'text-right' }]}>
                {roster.loading && <SkeletonRows rows={3} cols={2} />}
                {!roster.loading && !roster.error && students.length === 0 && (
                  <EmptyRow colSpan={2}>
                    <EmptyState icon={Users} title="No students in this class yet" />
                  </EmptyRow>
                )}
                {students.map((s) => (
                  <Row key={s.id}>
                    <Cell>
                      <div className="flex items-center gap-3">
                        <Avatar name={s.name} size="sm" />
                        <span className="font-medium text-slate-900 dark:text-white">{s.name}</span>
                      </div>
                    </Cell>
                    <Cell className="text-right font-mono text-xs text-slate-500 dark:text-slate-400">{s.roll_number}</Cell>
                  </Row>
                ))}
              </Table>
            </Card>

            <Card className="xl:col-span-3">
              <CardHeader icon={Clock} title="Class activity" description="Entries and exits recognized for your students" />
              <div className="max-h-[28rem] overflow-y-auto">
                <Table columns={[{ label: 'Event' }, { label: 'Student' }, { label: 'Time', className: 'text-right' }]}>
                  {roster.loading && <SkeletonRows rows={3} cols={3} />}
                  {!roster.loading && !roster.error && recent.length === 0 && (
                    <EmptyRow colSpan={3}>
                      <EmptyState icon={Clock} title="No activity yet" description="Your students' entries and exits will appear here." />
                    </EmptyRow>
                  )}
                  {recent.map((e, i) => (
                    <Row key={`${e.timestamp}-${i}`}>
                      <Cell><EventBadge type={e.type} /></Cell>
                      <Cell className="text-slate-700 dark:text-slate-200">{e.label}</Cell>
                      <Cell className="text-right text-xs tabular-nums text-slate-500 dark:text-slate-400">
                        <time dateTime={e.timestamp} title={e.timestamp}>{formatTime(e.timestamp)}</time>
                      </Cell>
                    </Row>
                  ))}
                </Table>
              </div>
            </Card>
          </div>
        </>
      )}
    </AppShell>
  )
}
