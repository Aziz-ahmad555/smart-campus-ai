import { useMemo, useState } from 'react'
import { Plus, Trash2, School, Users } from 'lucide-react'
import AppShell from '../components/layout/AppShell'
import { Button, IconButton } from '../components/ui/Button'
import { Card } from '../components/ui/Card'
import { Input } from '../components/ui/Field'
import { Modal, ConfirmDialog } from '../components/ui/Modal'
import { Avatar, PageHeader } from '../components/ui/Misc'
import { EmptyState, ErrorBanner, Skeleton } from '../components/ui/States'
import { useToast } from '../components/ui/Toast'
import { api } from '../lib/api'
import { useApi } from '../lib/useApi'

const EMPTY = { name: '', grade_level: '', section: '' }

export default function ClassesPage() {
  const toast = useToast()
  const classes = useApi('/classes', { auth: true, select: (d) => d.classes, initial: [] })
  const students = useApi('/students', { auth: true, select: (d) => d.students, initial: [] })

  const [creating, setCreating] = useState(false)
  const [form, setForm] = useState(EMPTY)
  const [formError, setFormError] = useState(null)
  const [saving, setSaving] = useState(false)
  const [deleting, setDeleting] = useState(null)
  const [busyDelete, setBusyDelete] = useState(false)

  const byClass = useMemo(() => {
    const map = {}
    for (const s of students.data) (map[s.class_id] ||= []).push(s)
    return map
  }, [students.data])
  const unassigned = byClass.null?.length || 0

  const create = async (e) => {
    e.preventDefault()
    if (!form.name.trim()) {
      setFormError('Class name is required.')
      return
    }
    setSaving(true)
    try {
      await api('/classes', { method: 'POST', auth: true, body: form })
      toast.success(`${form.name} was created.`)
      setCreating(false)
      classes.reload()
    } catch (err) {
      setFormError(err.message)
    } finally {
      setSaving(false)
    }
  }

  const remove = async () => {
    setBusyDelete(true)
    try {
      await api(`/classes/${deleting.id}`, { method: 'DELETE', auth: true })
      toast.success(`${deleting.name} was deleted.`)
      setDeleting(null)
      classes.reload()
      students.reload()
    } catch (err) {
      setDeleting(null)             // e.g. 409: the message says what to fix first
      toast.error(err.message)
    } finally {
      setBusyDelete(false)
    }
  }

  const openCreate = () => {
    setForm(EMPTY)
    setFormError(null)
    setCreating(true)
  }
  const set = (key) => (e) => setForm({ ...form, [key]: e.target.value })
  const deletingCount = deleting ? byClass[deleting.id]?.length || 0 : 0

  return (
    <AppShell>
      <PageHeader
        title="Classes"
        description={
          unassigned
            ? `Grades and sections. ${unassigned} student${unassigned === 1 ? ' is' : 's are'} not assigned to a class yet.`
            : 'Grades and sections, with the students assigned to each'
        }
        actions={<Button icon={Plus} onClick={openCreate}>Add class</Button>}
      />

      <ErrorBanner message={classes.error} onRetry={classes.reload} className="mb-6" />

      {classes.loading ? (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-3">
          {[0, 1, 2].map((i) => <Skeleton key={i} className="h-40 rounded-xl" />)}
        </div>
      ) : classes.error ? null : classes.data.length === 0 ? (
        <Card>
          <EmptyState
            icon={School}
            title="No classes yet"
            description="Create classes to group students and give teachers a class view."
            action={<Button icon={Plus} onClick={openCreate}>Add class</Button>}
          />
        </Card>
      ) : (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-3">
          {classes.data.map((c) => {
            const members = byClass[c.id] || []
            return (
              <Card key={c.id} className="group flex flex-col p-5 transition-shadow hover:shadow-md">
                <div className="flex items-start justify-between gap-3">
                  <div className="flex items-center gap-3">
                    <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-blue-50 text-blue-600 dark:bg-blue-500/10 dark:text-blue-400">
                      <School size={18} aria-hidden="true" />
                    </div>
                    <div>
                      <h3 className="font-semibold text-slate-900 dark:text-white">{c.name}</h3>
                      <p className="text-xs text-slate-500 dark:text-slate-400">
                        {[c.grade_level && `Grade ${c.grade_level}`, c.section && `Section ${c.section}`].filter(Boolean).join(' · ') || 'No grade or section'}
                      </p>
                    </div>
                  </div>
                  <IconButton icon={Trash2} label={`Delete ${c.name}`} tone="danger" onClick={() => setDeleting(c)} />
                </div>
                <div className="mt-5 flex items-center justify-between border-t border-slate-100 pt-4 dark:border-slate-800">
                  <p className="flex items-center gap-1.5 text-sm text-slate-600 dark:text-slate-300">
                    <Users size={15} aria-hidden="true" />
                    <span className="font-medium tabular-nums">{members.length}</span> student{members.length === 1 ? '' : 's'}
                  </p>
                  <div className="flex -space-x-2">
                    {members.slice(0, 4).map((s) => (
                      <span key={s.id} className="rounded-full ring-2 ring-white dark:ring-slate-900" title={s.name}>
                        <Avatar name={s.name} size="sm" />
                      </span>
                    ))}
                    {members.length > 4 && (
                      <span className="flex h-7 w-7 items-center justify-center rounded-full bg-slate-100 text-[11px] font-medium text-slate-600 ring-2 ring-white dark:bg-slate-800 dark:text-slate-300 dark:ring-slate-900">
                        +{members.length - 4}
                      </span>
                    )}
                  </div>
                </div>
              </Card>
            )
          })}
        </div>
      )}

      <Modal
        open={creating}
        onClose={() => setCreating(false)}
        title="Add class"
        footer={
          <>
            <Button variant="secondary" onClick={() => setCreating(false)}>Cancel</Button>
            <Button type="submit" form="class-form" loading={saving}>Create class</Button>
          </>
        }
      >
        <form id="class-form" onSubmit={create} className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          {formError && <ErrorBanner message={formError} className="sm:col-span-2" />}
          <div className="sm:col-span-2">
            <Input label="Class name" required maxLength={50} value={form.name} onChange={set('name')} placeholder="e.g. Grade 9 - A" />
          </div>
          <Input label="Grade level" maxLength={20} value={form.grade_level} onChange={set('grade_level')} placeholder="e.g. 9" />
          <Input label="Section" maxLength={10} value={form.section} onChange={set('section')} placeholder="e.g. A" />
        </form>
      </Modal>

      <ConfirmDialog
        open={deleting !== null}
        onClose={() => setDeleting(null)}
        onConfirm={remove}
        loading={busyDelete}
        title="Delete class?"
        message={
          deleting
            ? deletingCount
              ? `${deleting.name} still has ${deletingCount} student${deletingCount === 1 ? '' : 's'} assigned, so it can't be deleted until they are reassigned.`
              : `${deleting.name} will be deleted. This can't be undone.`
            : ''
        }
      />
    </AppShell>
  )
}
