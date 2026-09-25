import { useMemo, useState } from 'react'
import { Plus, Pencil, Trash2, Search, Briefcase } from 'lucide-react'
import AppShell from '../components/layout/AppShell'
import { Button, IconButton } from '../components/ui/Button'
import { Card } from '../components/ui/Card'
import { Badge } from '../components/ui/Badge'
import { Input, Select, SearchInput } from '../components/ui/Field'
import { Modal, ConfirmDialog } from '../components/ui/Modal'
import { Avatar, PageHeader, Tabs } from '../components/ui/Misc'
import { EmptyState, ErrorBanner, SkeletonRows } from '../components/ui/States'
import { Table, Row, Cell, EmptyRow } from '../components/ui/Table'
import { useToast } from '../components/ui/Toast'
import { api } from '../lib/api'
import { useApi } from '../lib/useApi'

const ROLES = ['Teacher', 'Security', 'Worker', 'Admin Staff', 'Other']
const EMPTY = { name: '', role: '', department: '', photo_folder: '' }

function roleTone(role) {
  const r = (role || '').toLowerCase()
  if (r.includes('teacher')) return 'info'
  if (r.includes('security') || r.includes('guard')) return 'warning'
  if (r.includes('admin')) return 'violet'
  return 'neutral'
}

export default function StaffPage() {
  const toast = useToast()
  const staff = useApi('/staff', { auth: true, select: (d) => d.staff, initial: [] })

  const [query, setQuery] = useState('')
  const [role, setRole] = useState('all')
  const [editing, setEditing] = useState(null)
  const [form, setForm] = useState(EMPTY)
  const [formError, setFormError] = useState(null)
  const [saving, setSaving] = useState(false)
  const [deleting, setDeleting] = useState(null)
  const [busyDelete, setBusyDelete] = useState(false)

  const shown = useMemo(() => {
    const q = query.trim().toLowerCase()
    return staff.data.filter(
      (p) =>
        (role === 'all' || p.role === role) &&
        (!q || [p.name, p.department, p.photo_folder].some((v) => (v || '').toLowerCase().includes(q))),
    )
  }, [staff.data, query, role])

  const roleCounts = (r) => staff.data.filter((p) => p.role === r).length

  const openForm = (person) => {
    setEditing(person || 'new')
    setForm(person ? { name: person.name, role: person.role, department: person.department || '', photo_folder: person.photo_folder } : EMPTY)
    setFormError(null)
  }

  const save = async (e) => {
    e.preventDefault()
    if (!form.name.trim() || !form.role || !form.photo_folder.trim()) {
      setFormError('Name, role and photo folder are required.')
      return
    }
    setSaving(true)
    const isNew = editing === 'new'
    try {
      await api(isNew ? '/staff' : `/staff/${editing.id}`, { method: isNew ? 'POST' : 'PUT', auth: true, body: form })
      toast.success(isNew ? `${form.name} was added.` : 'Changes saved.')
      setEditing(null)
      staff.reload()
    } catch (err) {
      setFormError(err.message)
    } finally {
      setSaving(false)
    }
  }

  const remove = async () => {
    setBusyDelete(true)
    try {
      await api(`/staff/${deleting.id}`, { method: 'DELETE', auth: true })
      toast.success(`${deleting.name} was removed.`)
      setDeleting(null)
      staff.reload()
    } catch (err) {
      toast.error(err.message)
    } finally {
      setBusyDelete(false)
    }
  }

  const set = (key) => (e) => setForm({ ...form, [key]: e.target.value })

  return (
    <AppShell>
      <PageHeader
        title="Staff"
        description="Teachers, security and other staff the recognition pipeline can identify"
        actions={<Button icon={Plus} onClick={() => openForm(null)}>Add staff member</Button>}
      />

      <ErrorBanner message={staff.error} onRetry={staff.reload} className="mb-6" />

      <Card>
        <div className="flex flex-col gap-3 border-b border-slate-100 px-5 py-3 lg:flex-row lg:items-center lg:justify-between dark:border-slate-800">
          <div className="overflow-x-auto">
            <Tabs
              label="Filter by role"
              value={role}
              onChange={setRole}
              options={[{ value: 'all', label: 'All', count: staff.data.length }, ...ROLES.map((r) => ({ value: r, label: r, count: roleCounts(r) }))]}
            />
          </div>
          <SearchInput value={query} onChange={setQuery} placeholder="Search name, department or folder" icon={Search} className="lg:w-80" />
        </div>

        <Table
          columns={[
            { label: 'Name' },
            { label: 'Role' },
            { label: 'Department', className: 'hidden md:table-cell' },
            { label: 'Photo folder', className: 'hidden lg:table-cell' },
            { label: <span className="sr-only">Actions</span>, key: 'actions' },
          ]}
        >
          {staff.loading && <SkeletonRows rows={3} cols={5} />}
          {!staff.loading && !staff.error && shown.length === 0 && (
            <EmptyRow colSpan={5}>
              {staff.data.length ? (
                <EmptyState icon={Search} title="No matching staff" description="Try a different search or role." />
              ) : (
                <EmptyState
                  icon={Briefcase}
                  title="No staff yet"
                  description="Add teachers and staff so the pipeline can recognize them on campus."
                  action={<Button icon={Plus} onClick={() => openForm(null)}>Add staff member</Button>}
                />
              )}
            </EmptyRow>
          )}
          {shown.map((p) => (
            <Row key={p.id}>
              <Cell>
                <div className="flex items-center gap-3">
                  <Avatar name={p.name} size="sm" />
                  <span className="font-medium text-slate-900 dark:text-white">{p.name}</span>
                </div>
              </Cell>
              <Cell><Badge tone={roleTone(p.role)}>{p.role}</Badge></Cell>
              <Cell className="hidden text-slate-600 md:table-cell dark:text-slate-300">{p.department || <span className="text-slate-400">—</span>}</Cell>
              <Cell className="hidden font-mono text-xs text-slate-500 lg:table-cell dark:text-slate-400">{p.photo_folder}</Cell>
              <Cell className="text-right">
                <div className="flex justify-end gap-1">
                  <IconButton icon={Pencil} label={`Edit ${p.name}`} onClick={() => openForm(p)} />
                  <IconButton icon={Trash2} label={`Delete ${p.name}`} tone="danger" onClick={() => setDeleting(p)} />
                </div>
              </Cell>
            </Row>
          ))}
        </Table>
      </Card>

      <Modal
        open={editing !== null}
        onClose={() => setEditing(null)}
        title={editing === 'new' ? 'Add staff member' : 'Edit staff member'}
        description="The photo folder links this record to reference photos used for face recognition."
        footer={
          <>
            <Button variant="secondary" onClick={() => setEditing(null)}>Cancel</Button>
            <Button type="submit" form="staff-form" loading={saving}>{editing === 'new' ? 'Add staff member' : 'Save changes'}</Button>
          </>
        }
      >
        <form id="staff-form" onSubmit={save} className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          {formError && <ErrorBanner message={formError} className="sm:col-span-2" />}
          <Input label="Full name" required value={form.name} onChange={set('name')} placeholder="Full name" autoComplete="off" />
          <Select label="Role" required value={form.role} onChange={set('role')}>
            <option value="">Select a role</option>
            {ROLES.map((r) => <option key={r} value={r}>{r}</option>)}
          </Select>
          <Input label="Department" value={form.department} onChange={set('department')} placeholder="e.g. Science, Maintenance" />
          <Input
            label="Photo folder"
            required
            value={form.photo_folder}
            onChange={set('photo_folder')}
            placeholder="e.g. KashifAli"
            hint="Folder name under data/known_faces/"
            className="font-mono"
          />
        </form>
      </Modal>

      <ConfirmDialog
        open={deleting !== null}
        onClose={() => setDeleting(null)}
        onConfirm={remove}
        loading={busyDelete}
        title="Delete staff member?"
        message={deleting ? `${deleting.name} will be removed from the directory. This can't be undone.` : ''}
      />
    </AppShell>
  )
}
