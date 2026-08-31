import { useState, useEffect } from 'react'
import { Plus, Trash2, Pencil, X, Check } from 'lucide-react'
import Sidebar from './Sidebar'

function StaffPage() {
  const [staff, setStaff] = useState([])
  const [darkMode, setDarkMode] = useState(false)
  const [showForm, setShowForm] = useState(false)
  const [editingId, setEditingId] = useState(null)
  const [formData, setFormData] = useState({ name: '', role: '', department: '', photo_folder: '' })
  const [error, setError] = useState(null)

  const fetchStaff = () => {
    fetch('http://localhost:8000/staff')
      .then((res) => res.json())
      .then((data) => setStaff(data.staff))
      .catch(() => setError('Could not load staff.'))
  }

  useEffect(() => { fetchStaff() }, [])

  useEffect(() => {
    if (darkMode) document.documentElement.classList.add('dark')
    else document.documentElement.classList.remove('dark')
  }, [darkMode])

  const resetForm = () => {
    setFormData({ name: '', role: '', department: '', photo_folder: '' })
    setEditingId(null)
    setShowForm(false)
    setError(null)
  }

  const handleSubmit = async () => {
    if (!formData.name || !formData.role || !formData.photo_folder) {
      setError('Name, role, and photo folder are required.')
      return
    }
    const token = localStorage.getItem('sentra_token')
    const baseUrl = editingId ? 'http://localhost:8000/staff/' + editingId : 'http://localhost:8000/staff'
    const url = baseUrl + '?token=' + token
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
      fetchStaff()
      resetForm()
    } catch (e) {
      setError(e.message)
    }
  }

  const handleEdit = (person) => {
    setFormData({ name: person.name, role: person.role, department: person.department || '', photo_folder: person.photo_folder })
    setEditingId(person.id)
    setShowForm(true)
  }

  const handleDelete = async (id) => {
    if (!confirm('Delete this staff record?')) return
    const token = localStorage.getItem('sentra_token')
    try {
      const res = await fetch('http://localhost:8000/staff/' + id + '?token=' + token, { method: 'DELETE' })
      if (!res.ok) {
        const err = await res.json()
        throw new Error(err.detail || 'Could not delete staff member.')
      }
      fetchStaff()
    } catch (e) {
      setError(e.message)
    }
  }

  const roleColor = (role) => {
    const r = (role || '').toLowerCase()
    if (r.includes('teacher')) return 'bg-blue-100 dark:bg-blue-900/30 text-blue-700 dark:text-blue-400'
    if (r.includes('security') || r.includes('guard')) return 'bg-rose-100 dark:bg-rose-900/30 text-rose-700 dark:text-rose-400'
    return 'bg-slate-100 dark:bg-slate-700 text-slate-700 dark:text-slate-200'
  }

  return (
    <div className="min-h-screen bg-slate-50 dark:bg-slate-900 transition-colors">
      <Sidebar darkMode={darkMode} setDarkMode={setDarkMode} />
      <div className="ml-64 p-8">
        <div className="flex items-center justify-between mb-8">
          <div>
            <h2 className="text-2xl font-bold text-slate-900 dark:text-white">Staff & Teachers</h2>
            <p className="text-sm text-slate-500 dark:text-slate-400 mt-1">
              Manage teachers, workers, and other staff identities in the recognition database
            </p>
          </div>
          <button onClick={() => { resetForm(); setShowForm(true) }}
            className="flex items-center gap-2 px-4 py-2 rounded-lg bg-slate-900 dark:bg-white text-white dark:text-slate-900 font-medium text-sm hover:opacity-90 transition-opacity">
            <Plus size={16} />
            Add Staff Member
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
              {editingId ? 'Edit Staff Member' : 'New Staff Member'}
            </h3>
            <div className="grid grid-cols-4 gap-4 mb-4">
              <div>
                <label className="text-xs text-slate-500 dark:text-slate-400 mb-1 block">Full Name</label>
                <input type="text" value={formData.name} onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                  className="w-full px-3 py-2 rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900 text-slate-900 dark:text-white text-sm" placeholder="Full name" />
              </div>
              <div>
                <label className="text-xs text-slate-500 dark:text-slate-400 mb-1 block">Role</label>
                <select value={formData.role} onChange={(e) => setFormData({ ...formData, role: e.target.value })}
                  className="w-full px-3 py-2 rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900 text-slate-900 dark:text-white text-sm">
                  <option value="">Select role</option>
                  <option value="Teacher">Teacher</option>
                  <option value="Security">Security</option>
                  <option value="Worker">Worker</option>
                  <option value="Admin Staff">Admin Staff</option>
                  <option value="Other">Other</option>
                </select>
              </div>
              <div>
                <label className="text-xs text-slate-500 dark:text-slate-400 mb-1 block">Department (optional)</label>
                <input type="text" value={formData.department} onChange={(e) => setFormData({ ...formData, department: e.target.value })}
                  className="w-full px-3 py-2 rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900 text-slate-900 dark:text-white text-sm" placeholder="e.g. Science, Maintenance" />
              </div>
              <div>
                <label className="text-xs text-slate-500 dark:text-slate-400 mb-1 block">Photo Folder Name</label>
                <input type="text" value={formData.photo_folder} onChange={(e) => setFormData({ ...formData, photo_folder: e.target.value })}
                  className="w-full px-3 py-2 rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900 text-slate-900 dark:text-white text-sm" placeholder="Matches data/known_faces/<folder>" />
              </div>
            </div>
            <div className="flex gap-2">
              <button onClick={handleSubmit} className="flex items-center gap-2 px-4 py-2 rounded-lg bg-emerald-600 text-white text-sm font-medium hover:bg-emerald-700 transition-colors">
                <Check size={16} />
                {editingId ? 'Save Changes' : 'Create Staff Member'}
              </button>
              <button onClick={resetForm} className="flex items-center gap-2 px-4 py-2 rounded-lg bg-slate-100 dark:bg-slate-700 text-slate-700 dark:text-slate-200 text-sm font-medium hover:bg-slate-200 dark:hover:bg-slate-600 transition-colors">
                <X size={16} />
                Cancel
              </button>
            </div>
          </div>
        )}

        <div className="bg-white dark:bg-slate-800 rounded-xl border border-slate-200 dark:border-slate-700 shadow-sm overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-slate-50 dark:bg-slate-900/50">
              <tr className="text-left text-xs text-slate-500 dark:text-slate-400 uppercase tracking-wide">
                <th className="px-5 py-3 font-medium">Name</th>
                <th className="px-5 py-3 font-medium">Role</th>
                <th className="px-5 py-3 font-medium">Department</th>
                <th className="px-5 py-3 font-medium">Photo Folder</th>
                <th className="px-5 py-3 font-medium text-right">Actions</th>
              </tr>
            </thead>
            <tbody>
              {staff.length === 0 && (
                <tr><td colSpan="5" className="px-5 py-8 text-center text-slate-400 text-sm">No staff registered yet.</td></tr>
              )}
              {staff.map((p) => (
                <tr key={p.id} className="border-t border-slate-100 dark:border-slate-700/50 hover:bg-slate-50 dark:hover:bg-slate-700/30">
                  <td className="px-5 py-3 text-slate-900 dark:text-white font-medium">{p.name}</td>
                  <td className="px-5 py-3">
                    <span className={'px-2.5 py-1 rounded-full text-xs font-semibold ' + roleColor(p.role)}>{p.role}</span>
                  </td>
                  <td className="px-5 py-3 text-slate-600 dark:text-slate-300">{p.department || '—'}</td>
                  <td className="px-5 py-3 text-slate-600 dark:text-slate-300 font-mono text-xs">{p.photo_folder}</td>
                  <td className="px-5 py-3 text-right">
                    <button onClick={() => handleEdit(p)} className="text-slate-400 hover:text-blue-500 mr-3 transition-colors">
                      <Pencil size={16} />
                    </button>
                    <button onClick={() => handleDelete(p.id)} className="text-slate-400 hover:text-rose-500 transition-colors">
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

export default StaffPage
