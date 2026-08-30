import { useState, useEffect } from 'react'
import { Plus, Trash2 } from 'lucide-react'
import Sidebar from './Sidebar'

function ClassesPage() {
  const [classes, setClasses] = useState([])
  const [darkMode, setDarkMode] = useState(false)
  const [showForm, setShowForm] = useState(false)
  const [error, setError] = useState(null)
  const [formData, setFormData] = useState({ name: '', grade_level: '', section: '' })

  const fetchClasses = () => {
    fetch('http://localhost:8000/classes')
      .then((res) => res.json())
      .then((data) => setClasses(data.classes))
      .catch(() => setError('Could not load classes.'))
  }

  useEffect(() => { fetchClasses() }, [])

  useEffect(() => {
    if (darkMode) document.documentElement.classList.add('dark')
    else document.documentElement.classList.remove('dark')
  }, [darkMode])

  const resetForm = () => {
    setFormData({ name: '', grade_level: '', section: '' })
    setShowForm(false)
    setError(null)
  }

  const handleCreate = async () => {
    if (!formData.name) {
      setError('Class name is required.')
      return
    }
    try {
      const res = await fetch('http://localhost:8000/classes', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(formData),
      })
      if (!res.ok) throw new Error('Could not create class.')
      fetchClasses()
      resetForm()
    } catch (e) {
      setError(e.message)
    }
  }

  const handleDelete = async (id) => {
    if (!confirm('Delete this class?')) return
    try {
      await fetch('http://localhost:8000/classes/' + id, { method: 'DELETE' })
      fetchClasses()
    } catch (e) {
      setError('Could not delete class.')
    }
  }

  return (
    <div className="min-h-screen bg-slate-50 dark:bg-slate-900 transition-colors">
      <Sidebar darkMode={darkMode} setDarkMode={setDarkMode} />
      <div className="ml-64 p-8">
        <div className="flex items-center justify-between mb-8">
          <div>
            <h2 className="text-2xl font-bold text-slate-900 dark:text-white">Classes & Grades</h2>
            <p className="text-sm text-slate-500 dark:text-slate-400 mt-1">
              Organize students by grade level and section
            </p>
          </div>
          <button onClick={() => { resetForm(); setShowForm(true) }}
            className="flex items-center gap-2 px-4 py-2 rounded-lg bg-slate-900 dark:bg-white text-white dark:text-slate-900 font-medium text-sm hover:opacity-90 transition-opacity">
            <Plus size={16} />
            Add Class
          </button>
        </div>

        {error && (
          <div className="mb-6 p-4 rounded-lg bg-rose-50 dark:bg-rose-900/20 border border-rose-200 dark:border-rose-800 text-rose-700 dark:text-rose-400 text-sm">
            {error}
          </div>
        )}

        {showForm && (
          <div className="mb-6 p-5 rounded-xl bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 shadow-sm">
            <h3 className="font-semibold text-slate-900 dark:text-white mb-4">New Class</h3>
            <div className="grid grid-cols-3 gap-4 mb-4">
              <div>
                <label className="text-xs text-slate-500 dark:text-slate-400 mb-1 block">Class Name</label>
                <input type="text" value={formData.name} onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                  className="w-full px-3 py-2 rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900 text-slate-900 dark:text-white text-sm" placeholder="e.g. Grade 9 - A" />
              </div>
              <div>
                <label className="text-xs text-slate-500 dark:text-slate-400 mb-1 block">Grade Level</label>
                <input type="text" value={formData.grade_level} onChange={(e) => setFormData({ ...formData, grade_level: e.target.value })}
                  className="w-full px-3 py-2 rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900 text-slate-900 dark:text-white text-sm" placeholder="e.g. 9" />
              </div>
              <div>
                <label className="text-xs text-slate-500 dark:text-slate-400 mb-1 block">Section</label>
                <input type="text" value={formData.section} onChange={(e) => setFormData({ ...formData, section: e.target.value })}
                  className="w-full px-3 py-2 rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900 text-slate-900 dark:text-white text-sm" placeholder="e.g. A" />
              </div>
            </div>
            <div className="flex gap-2">
              <button onClick={handleCreate} className="px-4 py-2 rounded-lg bg-emerald-600 text-white text-sm font-medium hover:bg-emerald-700 transition-colors">
                Create Class
              </button>
              <button onClick={resetForm} className="px-4 py-2 rounded-lg bg-slate-100 dark:bg-slate-700 text-slate-700 dark:text-slate-200 text-sm font-medium hover:bg-slate-200 dark:hover:bg-slate-600 transition-colors">
                Cancel
              </button>
            </div>
          </div>
        )}

        <div className="grid grid-cols-3 gap-4">
          {classes.length === 0 && (
            <p className="text-slate-400 text-sm col-span-3">No classes created yet.</p>
          )}
          {classes.map((c) => (
            <div key={c.id} className="bg-white dark:bg-slate-800 rounded-xl p-5 border border-slate-200 dark:border-slate-700 shadow-sm">
              <div className="flex items-start justify-between">
                <div>
                  <h3 className="font-semibold text-slate-900 dark:text-white">{c.name}</h3>
                  <p className="text-xs text-slate-500 dark:text-slate-400 mt-1">
                    {c.grade_level ? 'Grade ' + c.grade_level : ''} {c.section ? '• Section ' + c.section : ''}
                  </p>
                </div>
                <button onClick={() => handleDelete(c.id)} className="text-slate-400 hover:text-rose-500 transition-colors">
                  <Trash2 size={16} />
                </button>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}

export default ClassesPage
