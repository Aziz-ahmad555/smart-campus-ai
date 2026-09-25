import { useEffect, useMemo, useState } from 'react'
import { UserPlus, LogOut, Clock, AlertTriangle, UserCheck, History } from 'lucide-react'
import AppShell from '../components/layout/AppShell'
import { Button } from '../components/ui/Button'
import { Card } from '../components/ui/Card'
import { Badge } from '../components/ui/Badge'
import { Input } from '../components/ui/Field'
import { Modal } from '../components/ui/Modal'
import { Avatar, PageHeader, StatCard, Tabs } from '../components/ui/Misc'
import { EmptyState, ErrorBanner, SkeletonRows } from '../components/ui/States'
import { Table, Row, Cell, EmptyRow } from '../components/ui/Table'
import { useToast } from '../components/ui/Toast'
import { api } from '../lib/api'
import { formatDateTime, formatTime, parseTime } from '../lib/format'
import { useApi } from '../lib/useApi'

const EMPTY = { name: '', cnic_or_id: '', reason: '', host_name: '', allowed_minutes: 60 }
const STATUS = {
  checked_in: { tone: 'success', label: 'On campus' },
  overstayed: { tone: 'danger', label: 'Overstayed' },
  checked_out: { tone: 'neutral', label: 'Checked out' },
}

// Time left on the visit, derived from check-in + allowed minutes.
function Remaining({ visitor, now }) {
  const start = parseTime(visitor.check_in_time)
  const end = parseTime(visitor.expiry_time)
  if (!start || !end) return <span className="text-slate-400">—</span>
  const left = end - now
  const pct = Math.min(100, Math.max(0, ((now - start) / (end - start)) * 100))
  const over = left <= 0
  const mins = Math.floor(Math.abs(left) / 60000)
  const secs = Math.floor((Math.abs(left) % 60000) / 1000)
  const text = `${mins}m ${String(secs).padStart(2, '0')}s`
  return (
    <div className="w-36">
      <p className={`flex items-center gap-1 text-xs tabular-nums ${over ? 'font-medium text-rose-600 dark:text-rose-400' : 'text-slate-600 dark:text-slate-300'}`}>
        <Clock size={12} aria-hidden="true" />
        {over ? `${text} over` : `${text} left`}
      </p>
      <div className="mt-1.5 h-1 overflow-hidden rounded-full bg-slate-100 dark:bg-slate-800">
        <div
          className={`h-full rounded-full ${over ? 'bg-rose-500' : pct > 80 ? 'bg-amber-500' : 'bg-emerald-500'}`}
          style={{ width: `${over ? 100 : pct}%` }}
        />
      </div>
    </div>
  )
}

export default function VisitorsPage() {
  const toast = useToast()
  const visitors = useApi('/visitors', { select: (d) => d.visitors, initial: [], interval: 10000 })
  const [now, setNow] = useState(new Date())
  const [view, setView] = useState('active')
  const [open, setOpen] = useState(false)
  const [form, setForm] = useState(EMPTY)
  const [formError, setFormError] = useState(null)
  const [saving, setSaving] = useState(false)
  const [checkingOut, setCheckingOut] = useState(null)

  useEffect(() => {
    const tick = setInterval(() => setNow(new Date()), 1000)
    return () => clearInterval(tick)
  }, [])

  // Status is re-derived client-side every second so overstays show immediately.
  const list = useMemo(
    () =>
      visitors.data.map((v) => ({
        ...v,
        status: v.status === 'checked_out' ? 'checked_out' : parseTime(v.expiry_time) < now ? 'overstayed' : 'checked_in',
      })),
    [visitors.data, now],
  )
  const active = list.filter((v) => v.status !== 'checked_out')
  const overstayed = list.filter((v) => v.status === 'overstayed')
  const today = new Date().toDateString()
  const outToday = list.filter((v) => v.status === 'checked_out' && parseTime(v.check_out_time)?.toDateString() === today)
  const shown = view === 'active' ? active : list.filter((v) => v.status === 'checked_out')

  const checkIn = async (e) => {
    e.preventDefault()
    if (!form.name.trim()) {
      setFormError("The visitor's name is required.")
      return
    }
    if (!(form.allowed_minutes > 0)) {
      setFormError('Allowed duration must be at least 1 minute.')
      return
    }
    setSaving(true)
    try {
      await api('/visitors', { method: 'POST', auth: true, body: form })
      toast.success(`${form.name} is checked in.`)
      setOpen(false)
      setView('active')
      visitors.reload()
    } catch (err) {
      setFormError(err.message)
    } finally {
      setSaving(false)
    }
  }

  const checkOut = async (v) => {
    setCheckingOut(v.id)
    try {
      await api(`/visitors/${v.id}/checkout`, { method: 'PUT', auth: true })
      toast.success(`${v.name} is checked out.`)
      visitors.reload()
    } catch (err) {
      toast.error(err.message)
    } finally {
      setCheckingOut(null)
    }
  }

  const set = (key) => (e) => setForm({ ...form, [key]: e.target.value })

  return (
    <AppShell>
      <PageHeader
        title="Visitors"
        description="Check visitors in and out, and see who has stayed longer than allowed"
        actions={
          <Button icon={UserPlus} onClick={() => { setForm(EMPTY); setFormError(null); setOpen(true) }}>
            Check in visitor
          </Button>
        }
      />

      <ErrorBanner message={visitors.error} onRetry={visitors.reload} className="mb-6" />

      <div className="mb-6 grid grid-cols-1 gap-4 sm:grid-cols-3">
        <StatCard label="On campus" value={active.length} hint="Checked in and not yet out" icon={UserCheck} tone="emerald" loading={visitors.loading} />
        <StatCard
          label="Overstayed"
          value={overstayed.length}
          hint="Past their allowed time"
          icon={AlertTriangle}
          tone={overstayed.length ? 'rose' : 'slate'}
          loading={visitors.loading}
        />
        <StatCard label="Checked out today" value={outToday.length} icon={History} tone="slate" loading={visitors.loading} />
      </div>

      <Card>
        <div className="border-b border-slate-100 px-5 py-3 dark:border-slate-800">
          <Tabs
            label="Visitor list"
            value={view}
            onChange={setView}
            options={[
              { value: 'active', label: 'On campus', count: active.length },
              { value: 'history', label: 'Checked out', count: list.length - active.length },
            ]}
          />
        </div>
        <Table
          columns={[
            { label: 'Visitor' },
            { label: 'Visiting', className: 'hidden md:table-cell' },
            { label: 'Reason', className: 'hidden lg:table-cell' },
            { label: 'Checked in' },
            { label: view === 'active' ? 'Time' : 'Checked out' },
            { label: 'Status' },
            { label: <span className="sr-only">Actions</span>, key: 'actions' },
          ]}
        >
          {visitors.loading && <SkeletonRows rows={3} cols={7} />}
          {!visitors.loading && !visitors.error && shown.length === 0 && (
            <EmptyRow colSpan={7}>
              <EmptyState
                icon={view === 'active' ? UserCheck : History}
                title={view === 'active' ? 'No visitors on campus' : 'No past visits yet'}
                description={view === 'active' ? 'Visitors you check in appear here with a live countdown.' : 'Checked-out visits are kept here.'}
              />
            </EmptyRow>
          )}
          {shown.map((v) => (
            <Row key={v.id} className={v.status === 'overstayed' ? 'bg-rose-50/40 dark:bg-rose-500/[0.04]' : ''}>
              <Cell>
                <div className="flex items-center gap-3">
                  <Avatar name={v.name} size="sm" />
                  <div>
                    <p className="font-medium text-slate-900 dark:text-white">{v.name}</p>
                    {v.cnic_or_id && <p className="font-mono text-xs text-slate-500 dark:text-slate-400">{v.cnic_or_id}</p>}
                  </div>
                </div>
              </Cell>
              <Cell className="hidden text-slate-600 md:table-cell dark:text-slate-300">{v.host_name || <span className="text-slate-400">—</span>}</Cell>
              <Cell className="hidden text-slate-600 lg:table-cell dark:text-slate-300">{v.reason || <span className="text-slate-400">—</span>}</Cell>
              <Cell className="text-xs tabular-nums text-slate-500 dark:text-slate-400">{view === 'active' ? formatTime(v.check_in_time) : formatDateTime(v.check_in_time)}</Cell>
              <Cell>
                {view === 'active' ? (
                  <Remaining visitor={v} now={now} />
                ) : (
                  <span className="text-xs tabular-nums text-slate-500 dark:text-slate-400">{formatDateTime(v.check_out_time)}</span>
                )}
              </Cell>
              <Cell><Badge tone={STATUS[v.status].tone} dot>{STATUS[v.status].label}</Badge></Cell>
              <Cell className="text-right">
                {v.status !== 'checked_out' && (
                  <Button variant="secondary" size="sm" icon={LogOut} loading={checkingOut === v.id} onClick={() => checkOut(v)}>
                    Check out
                  </Button>
                )}
              </Cell>
            </Row>
          ))}
        </Table>
      </Card>

      <Modal
        open={open}
        onClose={() => setOpen(false)}
        title="Check in visitor"
        description="The visit is flagged as overstayed once the allowed time runs out."
        footer={
          <>
            <Button variant="secondary" onClick={() => setOpen(false)}>Cancel</Button>
            <Button type="submit" form="visitor-form" loading={saving}>Check in</Button>
          </>
        }
      >
        <form id="visitor-form" onSubmit={checkIn} className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          {formError && <ErrorBanner message={formError} className="sm:col-span-2" />}
          <Input label="Full name" required value={form.name} onChange={set('name')} placeholder="Visitor's name" autoComplete="off" />
          <Input label="CNIC / ID number" value={form.cnic_or_id} onChange={set('cnic_or_id')} placeholder="Optional" autoComplete="off" />
          <Input label="Visiting" value={form.host_name} onChange={set('host_name')} placeholder="e.g. Mr. Ahmed, Principal" />
          <Input label="Reason for visit" value={form.reason} onChange={set('reason')} placeholder="e.g. Parent meeting" />
          <Input
            label="Allowed duration (minutes)"
            type="number"
            min={1}
            max={1440}
            value={form.allowed_minutes}
            onChange={(e) => setForm({ ...form, allowed_minutes: parseInt(e.target.value, 10) || '' })}
          />
        </form>
      </Modal>
    </AppShell>
  )
}
