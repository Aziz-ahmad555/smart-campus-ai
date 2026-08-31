import { useState, useEffect } from 'react'
import { UserPlus, LogOut, Clock, AlertTriangle } from 'lucide-react'
import Sidebar from './Sidebar'

function formatRemaining(expiryTime) {
  const diff = new Date(expiryTime) - new Date()
  if (diff <= 0) return 'Overstayed'
  const mins = Math.floor(diff / 60000)
  const secs = Math.floor((diff % 60000) / 1000)
  return mins + 'm ' + secs + 's left'
}

function StatusBadge({ status }) {
  const config = {
    checked_in: { bg: 'bg-emerald-100 dark:bg-emerald-900/30', text: 'text-emerald-700 dark:text-emerald-400', label: 'On Campus' },
    overstayed: { bg: 'bg-rose-100 dark:bg-rose-900/30', text: 'text-rose-700 dark:text-rose-400', label: 'Overstayed' },
    checked_out: { bg: 'bg-slate-100 dark:bg-slate-700', text: 'text-slate-600 dark:text-slate-300', label: 'Checked Out' },
  }
  const c = config[status] || config.checked_in
  const cls = 'inline-flex items-center px-2.5 py-1 rounded-full text-xs font-semibold ' + c.bg + ' ' + c.text
  return <span className={cls}>{c.label}</span>
}

function VisitorsPage() {
  const [visitors, setVisitors] = useState([])
  const [darkMode, setDarkMode] = useState(false)
  const [showForm, setShowForm] = useState(false)
  const [error, setError] = useState(null)
  const [now, setNow] = useState(new Date())
  const [formData, setFormData] = useState({
    name: '', cnic_or_id: '', reason: '', host_name: '', allowed_minutes: 60
  })

  const fetchVisitors = () => {
    fetch('http://localhost:8000/visitors')
      .then((res) => res.json())
      .then((data) => setVisitors(data.visitors))
      .catch(() => setError('Could not load visitors.'))
  }

  useEffect(() => {
    fetchVisitors()
    const interval = setInterval(fetchVisitors, 5000)
    return () => clearInterval(interval)
  }, [])

  useEffect(() => {
    const tick = setInterval(() => setNow(new Date()), 1000)
    return () => clearInterval(tick)
  }, [])

  useEffect(() => {
    if (darkMode) document.documentElement.classList.add('dark')
    else document.documentElement.classList.remove('dark')
  }, [darkMode])

  const resetForm = () => {
    setFormData({ name: '', cnic_or_id: '', reason: '', host_name: '', allowed_minutes: 60 })
    setShowForm(false)
    setError(null)
  }

  const handleCheckIn = async () => {
    if (!formData.name) {
      setError('Visitor name is required.')
      return
    }
    const token = localStorage.getItem('sentra_token')
    try {
      const res = await fetch('http://localhost:8000/visitors?token=' + token, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(formData),
      })
      if (!res.ok) {
        const err = await res.json()
        throw new Error(err.detail || 'Check-in failed')
      }
      fetchVisitors()
      resetForm()
    } catch (e) {
      setError(e.message)
    }
  }

  const handleCheckOut = async (id) => {
    const token = localStorage.getItem('sentra_token')
    try {
      const res = await fetch('http://localhost:8000/visitors/' + id + '/checkout?token=' + token, { method: 'PUT' })
      if (!res.ok) {
        const err = await res.json()
        throw new Error(err.detail || 'Could not check out visitor.')
      }
      fetchVisitors()
    } catch (e) {
      setError(e.message)
    }
  }

  const onCampus = visitors.filter((v) => v.status !== 'checked_out')
  const overstayed = visitors.filter((v) => v.status === 'overstayed')

  return (
    <div className="min-h-screen bg-slate-50 dark:bg-slate-900 transition-colors">
      <Sidebar darkMode={darkMode} setDarkMode={setDarkMode} />

      <div className="ml-64 p-8">
        <div className="flex items-center justify-between mb-8">
          <div>
            <h2 className="text-2xl font-bold text-slate-900 dark:text-white">Visitor Management</h2>
            <p className="text-sm text-slate-500 dark:text-slate-400 mt-1">
              Manual check-in, duration tracking, and overstay alerts
            </p>
          </div>
          <button
            onClick={() => { resetForm(); setShowForm(true) }}
            className="flex items-center gap-2 px-4 py-2 rounded-lg bg-slate-900 dark:bg-white text-white dark:text-slate-900 font-medium text-sm hover:opacity-90 transition-opacity"
          >
            <UserPlus size={16} />
            Check In Visitor
          </button>
        </div>

        <div className="grid grid-cols-2 gap-4 mb-6">
          <div className="bg-white dark:bg-slate-800 rounded-xl p-5 border border-slate-200 dark:border-slate-700 shadow-sm">
            <p className="text-sm text-slate-500 dark:text-slate-400 font-medium">Currently On Campus</p>
            <p className="text-3xl font-bold text-slate-900 dark:text-white mt-1">{onCampus.length}</p>
          </div>
          <div className="bg-white dark:bg-slate-800 rounded-xl p-5 border border-slate-200 dark:border-slate-700 shadow-sm">
            <p className="text-sm text-slate-500 dark:text-slate-400 font-medium flex items-center gap-1">
              <AlertTriangle size={14} className="text-rose-500" />
              Overstayed
            </p>
            <p className="text-3xl font-bold text-rose-600 mt-1">{overstayed.length}</p>
          </div>
        </div>

        {error && (
          <div className="mb-6 p-4 rounded-lg bg-rose-50 dark:bg-rose-900/20 border border-rose-200 dark:border-rose-800 text-rose-700 dark:text-rose-400 text-sm">
            {error}
          </div>
        )}

        {showForm && (
          <div className="mb-6 p-5 rounded-xl bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 shadow-sm">
            <h3 className="font-semibold text-slate-900 dark:text-white mb-4">New Visitor Check-In</h3>
            <div className="grid grid-cols-3 gap-4 mb-4">
              <div>
                <label className="text-xs text-slate-500 dark:text-slate-400 mb-1 block">Full Name *</label>
                <input type="text" value={formData.name} onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                  className="w-full px-3 py-2 rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900 text-slate-900 dark:text-white text-sm" placeholder="Visitor's name" />
              </div>
              <div>
                <label className="text-xs text-slate-500 dark:text-slate-400 mb-1 block">CNIC / ID Number</label>
                <input type="text" value={formData.cnic_or_id} onChange={(e) => setFormData({ ...formData, cnic_or_id: e.target.value })}
                  className="w-full px-3 py-2 rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900 text-slate-900 dark:text-white text-sm" placeholder="Optional" />
              </div>
              <div>
                <label className="text-xs text-slate-500 dark:text-slate-400 mb-1 block">Visiting (Host Name)</label>
                <input type="text" value={formData.host_name} onChange={(e) => setFormData({ ...formData, host_name: e.target.value })}
                  className="w-full px-3 py-2 rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900 text-slate-900 dark:text-white text-sm" placeholder="e.g. Mr. Ahmed, Principal" />
              </div>
              <div>
                <label className="text-xs text-slate-500 dark:text-slate-400 mb-1 block">Reason for Visit</label>
                <input type="text" value={formData.reason} onChange={(e) => setFormData({ ...formData, reason: e.target.value })}
                  className="w-full px-3 py-2 rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900 text-slate-900 dark:text-white text-sm" placeholder="e.g. Parent meeting" />
              </div>
              <div>
                <label className="text-xs text-slate-500 dark:text-slate-400 mb-1 block">Allowed Duration (minutes)</label>
                <input type="number" value={formData.allowed_minutes} onChange={(e) => setFormData({ ...formData, allowed_minutes: parseInt(e.target.value) || 60 })}
                  className="w-full px-3 py-2 rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900 text-slate-900 dark:text-white text-sm" />
              </div>
            </div>
            <div className="flex gap-2">
              <button onClick={handleCheckIn} className="px-4 py-2 rounded-lg bg-emerald-600 text-white text-sm font-medium hover:bg-emerald-700 transition-colors">
                Check In
              </button>
              <button onClick={resetForm} className="px-4 py-2 rounded-lg bg-slate-100 dark:bg-slate-700 text-slate-700 dark:text-slate-200 text-sm font-medium hover:bg-slate-200 dark:hover:bg-slate-600 transition-colors">
                Cancel
              </button>
            </div>
          </div>
        )}

        <div className="bg-white dark:bg-slate-800 rounded-xl border border-slate-200 dark:border-slate-700 shadow-sm overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-slate-50 dark:bg-slate-900/50">
              <tr className="text-left text-xs text-slate-500 dark:text-slate-400 uppercase tracking-wide">
                <th className="px-5 py-3 font-medium">Visitor</th>
                <th className="px-5 py-3 font-medium">Visiting</th>
                <th className="px-5 py-3 font-medium">Reason</th>
                <th className="px-5 py-3 font-medium">Check-In</th>
                <th className="px-5 py-3 font-medium">Time Remaining</th>
                <th className="px-5 py-3 font-medium">Status</th>
                <th className="px-5 py-3 font-medium text-right">Action</th>
              </tr>
            </thead>
            <tbody>
              {visitors.length === 0 && (
                <tr><td colSpan="7" className="px-5 py-8 text-center text-slate-400 text-sm">No visitors recorded yet.</td></tr>
              )}
              {visitors.map((v) => (
                <tr key={v.id} className="border-t border-slate-100 dark:border-slate-700/50 hover:bg-slate-50 dark:hover:bg-slate-700/30">
                  <td className="px-5 py-3 text-slate-900 dark:text-white font-medium">{v.name}</td>
                  <td className="px-5 py-3 text-slate-600 dark:text-slate-300">{v.host_name || '—'}</td>
                  <td className="px-5 py-3 text-slate-600 dark:text-slate-300">{v.reason || '—'}</td>
                  <td className="px-5 py-3 text-slate-500 dark:text-slate-400 text-xs">{new Date(v.check_in_time).toLocaleTimeString()}</td>
                  <td className="px-5 py-3 text-xs">
                    {v.status === 'checked_out' ? (
                      <span className="text-slate-400">—</span>
                    ) : (
                      <span className={v.status === 'overstayed' ? 'text-rose-600 font-medium flex items-center gap-1' : 'text-slate-600 dark:text-slate-300 flex items-center gap-1'}>
                        <Clock size={12} />
                        {formatRemaining(v.expiry_time)}
                      </span>
                    )}
                  </td>
                  <td className="px-5 py-3"><StatusBadge status={v.status} /></td>
                  <td className="px-5 py-3 text-right">
                    {v.status !== 'checked_out' && (
                      <button onClick={() => handleCheckOut(v.id)} className="flex items-center gap-1 ml-auto text-xs text-slate-500 hover:text-blue-500 transition-colors">
                        <LogOut size={14} />
                        Check Out
                      </button>
                    )}
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

export default VisitorsPage
