import { useMemo, useState } from 'react'
import { KeyRound, Link2, Unlink, Fingerprint, Trash2, Search } from 'lucide-react'
import AppShell from '../components/layout/AppShell'
import { Button, IconButton } from '../components/ui/Button'
import { Card } from '../components/ui/Card'
import { Badge } from '../components/ui/Badge'
import { Select, SearchInput } from '../components/ui/Field'
import { Modal, ConfirmDialog } from '../components/ui/Modal'
import { Avatar, PageHeader, Tabs } from '../components/ui/Misc'
import { EmptyState, ErrorBanner, SkeletonRows } from '../components/ui/States'
import { Table, Row, Cell, EmptyRow } from '../components/ui/Table'
import { useToast } from '../components/ui/Toast'
import { api } from '../lib/api'
import { formatDate } from '../lib/format'
import { getUser } from '../lib/session'
import { useApi } from '../lib/useApi'

const ROLE = {
  admin: { tone: 'violet', label: 'Admin' },
  teacher: { tone: 'info', label: 'Teacher' },
  student: { tone: 'success', label: 'Student' },
}

// What a confirm dialog is about to do.
const ACTIONS = {
  unlink: {
    title: 'Unlink account?',
    message: (u) => `${u.username} will no longer be linked to ${u.linked_name}, so their own views will be empty until it's linked again.`,
    label: 'Unlink',
  },
  fingerprints: {
    title: 'Remove fingerprints?',
    message: (u) => `${u.username}'s ${u.fingerprints} registered fingerprint${u.fingerprints === 1 ? '' : 's'} will be removed. They can still sign in with their password.`,
    label: 'Remove',
  },
  delete: {
    title: 'Delete account?',
    message: (u) => `The sign-in account ${u.username} will be deleted and signed out everywhere. Their student or staff record is kept. This can't be undone.`,
    label: 'Delete',
  },
}

export default function UsersPage() {
  const toast = useToast()
  const me = getUser()
  const users = useApi('/users', { auth: true, select: (d) => d.users, initial: [] })
  const students = useApi('/students', { auth: true, select: (d) => d.students, initial: [] })
  const staff = useApi('/staff', { auth: true, select: (d) => d.staff, initial: [] })

  const [role, setRole] = useState('all')
  const [query, setQuery] = useState('')
  const [linking, setLinking] = useState(null)       // user being linked
  const [personId, setPersonId] = useState('')
  const [saving, setSaving] = useState(false)
  const [pending, setPending] = useState(null)       // { action, user }
  const [busy, setBusy] = useState(false)

  const shown = useMemo(() => {
    const q = query.trim().toLowerCase()
    return users.data.filter(
      (u) =>
        (role === 'all' || u.role === role) &&
        (!q || [u.username, u.full_name, u.linked_name].some((v) => (v || '').toLowerCase().includes(q))),
    )
  }, [users.data, role, query])
  const unlinked = users.data.filter((u) => u.role !== 'admin' && !u.linked_name).length

  const openLink = (user) => {
    setLinking(user)
    setPersonId(String(user.student_id ?? user.staff_id ?? ''))
  }

  const saveLink = async (e) => {
    e.preventDefault()
    setSaving(true)
    try {
      await api(`/users/${linking.id}/link`, { method: 'PUT', auth: true, body: { person_id: personId ? Number(personId) : null } })
      toast.success(`${linking.username} is linked.`)
      setLinking(null)
      users.reload()
    } catch (err) {
      toast.error(err.message)
    } finally {
      setSaving(false)
    }
  }

  const confirm = async () => {
    const { action, user } = pending
    setBusy(true)
    try {
      if (action === 'unlink') await api(`/users/${user.id}/link`, { method: 'PUT', auth: true, body: { person_id: null } })
      if (action === 'fingerprints') await api(`/users/${user.id}/fingerprints`, { method: 'DELETE', auth: true })
      if (action === 'delete') await api(`/users/${user.id}`, { method: 'DELETE', auth: true })
      toast.success(action === 'delete' ? `${user.username} was deleted.` : action === 'unlink' ? `${user.username} is unlinked.` : 'Fingerprints removed.')
      users.reload()
    } catch (err) {
      toast.error(err.message)      // e.g. 409: remove their fingerprints first
    } finally {
      setPending(null)
      setBusy(false)
    }
  }

  const people = linking?.role === 'student' ? students.data : staff.data

  return (
    <AppShell>
      <PageHeader
        title="Accounts"
        description={
          unlinked
            ? `Sign-in accounts. ${unlinked} teacher or student account${unlinked === 1 ? ' is' : 's are'} not linked to a person yet.`
            : 'Sign-in accounts and the student or staff record each one belongs to'
        }
      />

      <ErrorBanner message={users.error} onRetry={users.reload} className="mb-6" />

      <Card>
        <div className="flex flex-col gap-3 border-b border-slate-100 px-5 py-3 sm:flex-row sm:items-center sm:justify-between dark:border-slate-800">
          <Tabs
            label="Filter by role"
            value={role}
            onChange={setRole}
            options={[
              { value: 'all', label: 'All', count: users.data.length },
              ...Object.entries(ROLE).map(([value, r]) => ({ value, label: r.label, count: users.data.filter((u) => u.role === value).length })),
            ]}
          />
          <SearchInput value={query} onChange={setQuery} placeholder="Search username or name" icon={Search} className="sm:w-72" />
        </div>

        <Table
          columns={[
            { label: 'Account' },
            { label: 'Role' },
            { label: 'Linked to' },
            { label: 'Fingerprints', className: 'hidden md:table-cell' },
            { label: 'Created', className: 'hidden lg:table-cell' },
            { label: <span className="sr-only">Actions</span>, key: 'actions' },
          ]}
        >
          {users.loading && <SkeletonRows rows={3} cols={6} />}
          {!users.loading && !users.error && shown.length === 0 && (
            <EmptyRow colSpan={6}>
              <EmptyState icon={KeyRound} title={users.data.length ? 'No matching accounts' : 'No accounts yet'} />
            </EmptyRow>
          )}
          {shown.map((u) => {
            const isMe = me?.username === u.username
            return (
              <Row key={u.id}>
                <Cell>
                  <div className="flex items-center gap-3">
                    <Avatar name={u.full_name || u.username} size="sm" />
                    <div>
                      <p className="font-medium text-slate-900 dark:text-white">
                        {u.username}
                        {isMe && <span className="ml-2 text-xs font-normal text-slate-400">(you)</span>}
                      </p>
                      {u.full_name && <p className="text-xs text-slate-500 dark:text-slate-400">{u.full_name}</p>}
                    </div>
                  </div>
                </Cell>
                <Cell><Badge tone={ROLE[u.role]?.tone || 'neutral'}>{ROLE[u.role]?.label || u.role}</Badge></Cell>
                <Cell>
                  {u.role === 'admin' ? (
                    <span className="text-slate-400">—</span>
                  ) : u.linked_name ? (
                    <span className="text-slate-700 dark:text-slate-200">
                      {u.linked_name}
                      {u.linked_roll_number && <span className="ml-1.5 font-mono text-xs text-slate-400">{u.linked_roll_number}</span>}
                    </span>
                  ) : (
                    <Badge tone="warning">Not linked</Badge>
                  )}
                </Cell>
                <Cell className="hidden md:table-cell">
                  {u.fingerprints ? (
                    <span className="inline-flex items-center gap-1.5 text-slate-600 dark:text-slate-300">
                      <Fingerprint size={14} aria-hidden="true" />
                      {u.fingerprints}
                    </span>
                  ) : (
                    <span className="text-xs text-slate-400">None</span>
                  )}
                </Cell>
                <Cell className="hidden text-xs text-slate-500 lg:table-cell dark:text-slate-400">{formatDate(u.created_at)}</Cell>
                <Cell className="text-right">
                  <div className="flex justify-end gap-1">
                    {u.role !== 'admin' && <IconButton icon={Link2} label={`Link ${u.username}`} onClick={() => openLink(u)} />}
                    {u.role !== 'admin' && u.linked_name && (
                      <IconButton icon={Unlink} label={`Unlink ${u.username}`} onClick={() => setPending({ action: 'unlink', user: u })} />
                    )}
                    {u.fingerprints > 0 && (
                      <IconButton icon={Fingerprint} label={`Remove ${u.username}'s fingerprints`} onClick={() => setPending({ action: 'fingerprints', user: u })} />
                    )}
                    {!isMe && (
                      <IconButton icon={Trash2} label={`Delete ${u.username}`} tone="danger" onClick={() => setPending({ action: 'delete', user: u })} />
                    )}
                  </div>
                </Cell>
              </Row>
            )
          })}
        </Table>
      </Card>

      <p className="mt-4 text-xs text-slate-500 dark:text-slate-400">
        New accounts are created with <span className="font-mono">backend/database/create_user.py</span>.
      </p>

      <Modal
        open={linking !== null}
        onClose={() => setLinking(null)}
        title={linking ? `Link ${linking.username}` : ''}
        description={linking?.role === 'student'
          ? "Choose the student record this account belongs to. Their profile then shows that student's activity."
          : "Choose the staff record this teacher account belongs to. Their class view then shows that teacher's class."}
        footer={
          <>
            <Button variant="secondary" onClick={() => setLinking(null)}>Cancel</Button>
            <Button type="submit" form="link-form" loading={saving}>Save link</Button>
          </>
        }
      >
        <form id="link-form" onSubmit={saveLink}>
          <Select label={linking?.role === 'student' ? 'Student' : 'Staff member'} value={personId} onChange={(e) => setPersonId(e.target.value)}>
            <option value="">Not linked</option>
            {people.map((p) => (
              <option key={p.id} value={p.id}>
                {p.name}{p.roll_number ? ` (${p.roll_number})` : p.role ? ` (${p.role})` : ''}
              </option>
            ))}
          </Select>
        </form>
      </Modal>

      <ConfirmDialog
        open={pending !== null}
        onClose={() => setPending(null)}
        onConfirm={confirm}
        loading={busy}
        title={pending ? ACTIONS[pending.action].title : ''}
        message={pending ? ACTIONS[pending.action].message(pending.user) : ''}
        confirmLabel={pending ? ACTIONS[pending.action].label : ''}
      />
    </AppShell>
  )
}
