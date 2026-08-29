import { useState, useEffect } from 'react'
import { Plus, Trash2, Pencil, X, Check } from 'lucide-react'
import Sidebar from './Sidebar'

function StudentsPage() {
  const [students, setStudents] = useState([])
  const [darkMode, setDarkMode] = useState(false)
  const [showForm, setShowForm] = useState(false)
  const [editingId, setEditingId] = useState(null)
  const [formData, setFormData] = useState({ name: '', roll_number: '', photo_folder: '' })
  const [error, setError] = useState(null)

  const fetchStudents = () => {
    fetch('http://localhost:8000/students')
      .then((res) => res.json())
      .then((data) => setStudents(data.students))
      .catch(() => setError('Could not load students.'))
  }

  useEffect(() => {
    fetchStudents()
  }, [])

  useEffect(() => {
    if (darkMode) document.documentElement.classList.add('dark')
    else document.documentElement.classList.remove('dark')
  }, [darkMode])

  const resetForm = () => {
    setFormData({ name: '', roll_number: '', photo_folder: '' })
    setEditingId(null)
    setShowForm(false)
    setError(null)
  }

  const handleSubmit = async () => {
    if (!formData.name || !formData.roll_number || !formData.photo_folder) {
      setError('All fields are required.')
      return
    }
    const url = editingId
      ? 'http://localhost:8000/students/' + editingId
      : 'http://localhost:8000/students'
    const method = editingId ? 'PUT' : 'POST'

    try {
      const res = await fetch(url, {
        method,
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(formData),
      })
      if (!res.ok) {
        const err = await res.json()
        throw new Error(err.detail || 'Request failed')
      }
      fetchStudents()
      resetForm()
    } catch (e) {
      setError(e.message)
    }
  }

  const handleEdit = (student) => {
    setFormData({ name: student.name, roll_number: student.roll_number, photo_folder: student.photo_folder })
    setEditingId(student.id)
    setShowForm(true)
  }

  const handleDelete = async (id) => {
    if (!confirm('Delete this student record?')) return
    try {
      await fetch('http://localhost:8000/students/' + id, { method: 'DELETE' })
      fetchStudents()
    } catch (e) {
      setError('Could not delete student.')
    }
  }

  return (
    <div className="min-h-screen bg-slate-50 dark:bg-slate-900 transition-colors">
      <Sidebar darkMode={darkMode} setDarkMode={setDarkMode} />

      <div className="ml-64 p-8">
        <div className="flex items-center justify-between mb-8">
          <div>
            <h2 className="text-2xl font-bold text-slate-900 dark:text-white">Student Records</h2>
            <p className="text-sm text-slate-500 dark:text-slate-400 mt-1">
              Manage identities registered in the recognition database
            </p>
          </div>
          <button
            onClick={() => { resetForm(); setShowForm(true) }}
            className="flex items-center gap-2 px-4 py-2 rounded-lg bg-slate-900 dark:bg-white text-white dark:text-slate-900 font-medium text-sm hover:opacity-90 transition-opacity"
          >
            <Plus size={16} />
            Add Student
          </button>
        </div>

        {error && (
          <div className="mb-6 p-4 rounded-lg bg-rose-50 dark:bg-rose-900/20 border border-rose-200 dark:border-rose-800 text-rose-700 dark:text-rose-400 text-sm">
            {error}
          </div>
        )}

        {showForm && (
          <div className="mb-6 p-5 rounded-xl bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 shadow-sm">
            <h3 className="font-semibold text-slate-900 dark:text-white mb-4">
              {editingId ? 'Edit Student' : 'New Student'}
            </h3>
            <div className="grid grid-cols-3 gap-4 mb-4">
              <div>
                <label className="text-xs text-slate-500 dark:text-slate-400 mb-1 block">Full Name</label>
                <input
                  type="text"
                  value={formData.name}
                  onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                  className="w-full px-3 py-2 rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900 text-slate-900 dark:text-white text-sm"
                  placeholder="e.g. Aziz Ahmad"
                />
              </div>
              <div>
                <label className="text-xs text-slate-500 dark:text-slate-400 mb-1 block">Roll Number</label>
                <input
                  type="text"
                  value={formData.roll_number}
                  onChange={(e) => setFormData({ ...formData, roll_number: e.target.value })}
                  className="w-full px-3 py-2 rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900 text-slate-900 dark:text-white text-sm"
                  placeholder="e.g. CS-002"
                />
              </div>
              <div>
                <label className="text-xs text-slate-500 dark:text-slate-400 mb-1 block">Photo Folder Name</label>
                <input
                  type="text"
                  value={formData.photo_folder}
                  onChange={(e) => setFormData({ ...formData, photo_folder: e.target.value })}
                  className="w-full px-3 py-2 rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900 text-slate-900 dark:text-white text-sm"
                  placeholder="Matches data/known_faces/<folder>"
                />
              </div>
            </div>
            <div className="flex gap-2">
              <button
                onClick={handleSubmit}
                className="flex items-center gap-2 px-4 py-2 rounded-lg bg-emerald-600 text-white text-sm font-medium hover:bg-emerald-700 transition-colors"
              >
                <Check size={16} />
                {editingId ? 'Save Changes' : 'Create Student'}
              </button>
              <button
                onClick={resetForm}
                className="flex items-center gap-2 px-4 py-2 rounded-lg bg-slate-100 dark:bg-slate-700 text-slate-700 dark:text-slate-200 text-sm font-medium hover:bg-slate-200 dark:hover:bg-slate-600 transition-colors"
              >
                <X size={16} />
                Cancel
              </button>
            </div>
            <p className="text-xs text-slate-400 mt-3">
              Note: "Photo Folder Name" must match a folder under data/known_faces/ containing reference photos for this identity.
            </p>
          </div>
        )}

        <div className="bg-white dark:bg-slate-800 rounded-xl border border-slate-200 dark:border-slate-700 shadow-sm overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-slate-50 dark:bg-slate-900/50">
              <tr className="text-left text-xs text-slate-500 dark:text-slate-400 uppercase tracking-wide">
                <th className="px-5 py-3 font-medium">ID</th>
                <th className="px-5 py-3 font-medium">Name</th>
                <th className="px-5 py-3 font-medium">Roll Number</th>
                <th className="px-5 py-3 font-medium">Photo Folder</th>
                <th className="px-5 py-3 font-medium">Registered</th>
                <th className="px-5 py-3 font-medium text-right">Actions</th>
              </tr>
            </thead>
            <tbody>
              {students.length === 0 && (
                <tr>
                  <td colSpan="6" className="px-5 py-8 text-center text-slate-400 text-sm">
                    No students registered yet.
                  </td>
                </tr>
              )}
              {students.map((s) => (
                <tr key={s.id} className="border-t border-slate-100 dark:border-slate-700/50 hover:bg-slate-50 dark:hover:bg-slate-700/30">
                  <td className="px-5 py-3 text-slate-500 dark:text-slate-400 font-mono text-xs">{s.id}</td>
                  <td className="px-5 py-3 text-slate-900 dark:text-white font-medium">{s.name}</td>
                  <td className="px-5 py-3 text-slate-600 dark:text-slate-300">{s.roll_number}</td>
                  <td className="px-5 py-3 text-slate-600 dark:text-slate-300 font-mono text-xs">{s.photo_folder}</td>
                  <td className="px-5 py-3 text-slate-500 dark:text-slate-400 text-xs">{s.created_at}</td>
                  <td className="px-5 py-3 text-right">
                    <button onClick={() => handleEdit(s)} className="text-slate-400 hover:text-blue-500 mr-3 transition-colors">
                      <Pencil size={16} />
                    </button>
                    <button onClick={() => handleDelete(s.id)} className="text-slate-400 hover:text-rose-500 transition-colors">
                      <Trash2 size={16} />
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}

export default StudentsPage
