import { useMemo, useState } from 'react'
import { Plus, Pencil, Trash2, Search, GraduationCap } from 'lucide-react'
import AppShell from '../components/layout/AppShell'
import { Button, IconButton } from '../components/ui/Button'
import { Card } from '../components/ui/Card'
import { Badge } from '../components/ui/Badge'
import { Input, Select, SearchInput } from '../components/ui/Field'
import { Modal, ConfirmDialog } from '../components/ui/Modal'
import { Avatar, PageHeader } from '../components/ui/Misc'
import { EmptyState, ErrorBanner, SkeletonRows } from '../components/ui/States'
import { Table, Row, Cell, EmptyRow } from '../components/ui/Table'
import { useToast } from '../components/ui/Toast'
import { api } from '../lib/api'
import { formatDate } from '../lib/format'
import { useApi } from '../lib/useApi'

const EMPTY = { name: '', roll_number: '', photo_folder: '', class_id: '' }

export default function StudentsPage() {
  const toast = useToast()
  const students = useApi('/students', { select: (d) => d.students, initial: [] })
  const classes = useApi('/classes', { select: (d) => d.classes, initial: [] })

  const [query, setQuery] = useState('')
  const [classFilter, setClassFilter] = useState('')
  const [editing, setEditing] = useState(null) // null | 'new' | student
  const [form, setForm] = useState(EMPTY)
  const [formError, setFormError] = useState(null)
  const [saving, setSaving] = useState(false)
  const [deleting, setDeleting] = useState(null)
  const [busyDelete, setBusyDelete] = useState(false)

  const shown = useMemo(() => {
    const q = query.trim().toLowerCase()
    return students.data.filter(
      (s) =>
        (!q || [s.name, s.roll_number, s.photo_folder].some((v) => (v || '').toLowerCase().includes(q))) &&
        (!classFilter || String(s.class_id ?? 'none') === classFilter),
    )
  }, [students.data, query, classFilter])

  const openForm = (student) => {
    setEditing(student || 'new')
    setForm(student
      ? { name: student.name, roll_number: student.roll_number, photo_folder: student.photo_folder, class_id: student.class_id ? String(student.class_id) : '' }
      : EMPTY)
    setFormError(null)
  }

  const save = async (e) => {
    e.preventDefault()
    if (!form.name.trim() || !form.roll_number.trim() || !form.photo_folder.trim()) {
      setFormError('Name, roll number and photo folder are required.')
      return
    }
    setSaving(true)
    const isNew = editing === 'new'
    try {
      await api(isNew ? '/students' : `/students/${editing.id}`, {
        method: isNew ? 'POST' : 'PUT',
        auth: true,
        body: { ...form, class_id: form.class_id ? Number(form.class_id) : null },
      })
      toast.success(isNew ? `${form.name} was added.` : 'Changes saved.')
      setEditing(null)
      students.reload()
    } catch (err) {
      setFormError(err.message)
    } finally {
      setSaving(false)
    }
  }

  const remove = async () => {
    setBusyDelete(true)
    try {
      await api(`/students/${deleting.id}`, { method: 'DELETE', auth: true })
      toast.success(`${deleting.name} was removed.`)
      setDeleting(null)
      students.reload()
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
        title="Students"
        description="People the recognition pipeline can identify as students"
        actions={<Button icon={Plus} onClick={() => openForm(null)}>Add student</Button>}
      />

      <ErrorBanner message={students.error} onRetry={students.reload} className="mb-6" />

      <Card>
        <div className="flex flex-col gap-3 border-b border-slate-100 px-5 py-3 sm:flex-row sm:items-center dark:border-slate-800">
          <SearchInput value={query} onChange={setQuery} placeholder="Search name, roll number or folder" icon={Search} className="sm:w-80" />
          <select
            value={classFilter}
            onChange={(e) => setClassFilter(e.target.value)}
            aria-label="Filter by class"
            className="h-9 rounded-lg border border-slate-200 bg-white px-3 text-sm text-slate-700 shadow-sm focus:border-blue-500 focus:outline-none dark:border-slate-700 dark:bg-slate-950 dark:text-slate-200"
          >
            <option value="">All classes</option>
            {classes.data.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
            <option value="none">Unassigned</option>
          </select>
          <p className="text-xs text-slate-500 sm:ml-auto dark:text-slate-400">
            {shown.length} of {students.data.length} students
          </p>
        </div>

        <Table
          columns={[
            { label: 'Student' },
            { label: 'Roll number' },
            { label: 'Class' },
            { label: 'Photo folder', className: 'hidden lg:table-cell' },
            { label: 'Registered', className: 'hidden md:table-cell' },
            { label: <span className="sr-only">Actions</span>, key: 'actions' },
          ]}
        >
          {students.loading && <SkeletonRows rows={4} cols={6} />}
          {!students.loading && !students.error && shown.length === 0 && (
            <EmptyRow colSpan={6}>
              {students.data.length ? (
                <EmptyState icon={Search} title="No matching students" description="Try a different search or class filter." />
              ) : (
                <EmptyState
                  icon={GraduationCap}
                  title="No students yet"
                  description="Add a student and point them to their reference photos so they can be recognized."
                  action={<Button icon={Plus} onClick={() => openForm(null)}>Add student</Button>}
                />
              )}
            </EmptyRow>
          )}
          {shown.map((s) => (
            <Row key={s.id}>
              <Cell>
                <div className="flex items-center gap-3">
                  <Avatar name={s.name} size="sm" />
                  <span className="font-medium text-slate-900 dark:text-white">{s.name}</span>
                </div>
              </Cell>
              <Cell className="font-mono text-xs text-slate-600 dark:text-slate-300">{s.roll_number}</Cell>
              <Cell>{s.class_name ? <Badge tone="info">{s.class_name}</Badge> : <span className="text-xs text-slate-400">Unassigned</span>}</Cell>
              <Cell className="hidden font-mono text-xs text-slate-500 lg:table-cell dark:text-slate-400">{s.photo_folder}</Cell>
              <Cell className="hidden text-xs text-slate-500 md:table-cell dark:text-slate-400">{formatDate(s.created_at)}</Cell>
              <Cell className="text-right">
                <div className="flex justify-end gap-1">
                  <IconButton icon={Pencil} label={`Edit ${s.name}`} onClick={() => openForm(s)} />
                  <IconButton icon={Trash2} label={`Delete ${s.name}`} tone="danger" onClick={() => setDeleting(s)} />
                </div>
              </Cell>
            </Row>
          ))}
        </Table>
      </Card>

      <Modal
        open={editing !== null}
        onClose={() => setEditing(null)}
        title={editing === 'new' ? 'Add student' : 'Edit student'}
        description="The photo folder links this record to reference photos used for face recognition."
        footer={
          <>
            <Button variant="secondary" onClick={() => setEditing(null)}>Cancel</Button>
            <Button type="submit" form="student-form" loading={saving}>{editing === 'new' ? 'Add student' : 'Save changes'}</Button>
          </>
        }
      >
        <form id="student-form" onSubmit={save} className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          {formError && <ErrorBanner message={formError} className="sm:col-span-2" />}
          <Input label="Full name" required value={form.name} onChange={set('name')} placeholder="e.g. Aziz Ahmad" autoComplete="off" />
          <Input label="Roll number" required value={form.roll_number} onChange={set('roll_number')} placeholder="e.g. CS-002" autoComplete="off" />
          <Select label="Class" value={form.class_id} onChange={set('class_id')}>
            <option value="">Unassigned</option>
            {classes.data.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
          </Select>
          <Input
            label="Photo folder"
            required
            value={form.photo_folder}
            onChange={set('photo_folder')}
            placeholder="e.g. AzizAhmad"
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
        title="Delete student?"
        message={deleting ? `${deleting.name} (${deleting.roll_number}) will be removed from the directory. This can't be undone.` : ''}
      />
    </AppShell>
  )
}
