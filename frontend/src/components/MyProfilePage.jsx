import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { LogOut, Clock } from 'lucide-react'

function MyProfilePage() {
  const navigate = useNavigate()
  const [events, setEvents] = useState([])
  const userJson = localStorage.getItem('sentra_user')
  const user = userJson ? JSON.parse(userJson) : null

  useEffect(() => {
    fetch('http://localhost:8000/events')
      .then((res) => res.json())
      .then((data) => setEvents(data.events))
      .catch(() => {})
  }, [])

  const handleLogout = async () => {
    const token = localStorage.getItem('sentra_token')
    try {
      await fetch('http://localhost:8000/logout?token=' + token, { method: 'POST' })
    } catch (e) {}
    localStorage.removeItem('sentra_token')
    localStorage.removeItem('sentra_user')
    navigate('/login')
  }

  // Filter events to this student's own name, if linked
  const myEvents = events.filter((e) => user && e.label && e.label.includes(user.full_name))

  return (
    <div className="min-h-screen bg-slate-50 dark:bg-slate-900 p-8">
      <div className="max-w-2xl mx-auto">
        <div className="flex items-center justify-between mb-8">
          <div>
            <h2 className="text-2xl font-bold text-slate-900 dark:text-white">My Profile</h2>
            <p className="text-sm text-slate-500 dark:text-slate-400 mt-1">
              Welcome, {user ? user.full_name : 'Student'}
            </p>
          </div>
          <button onClick={handleLogout} className="flex items-center gap-2 px-4 py-2 rounded-lg bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-200 text-sm font-medium hover:bg-slate-200 dark:hover:bg-slate-700 transition-colors">
            <LogOut size={16} />
            Log Out
          </button>
        </div>

        <div className="bg-white dark:bg-slate-800 rounded-xl border border-slate-200 dark:border-slate-700 shadow-sm overflow-hidden">
          <div className="p-5 border-b border-slate-200 dark:border-slate-700">
            <h3 className="font-semibold text-slate-900 dark:text-white flex items-center gap-2">
              <Clock size={16} />
              My Recent Campus Activity
            </h3>
          </div>
          <table className="w-full text-sm">
            <thead className="bg-slate-50 dark:bg-slate-900/50">
              <tr className="text-left text-xs text-slate-500 dark:text-slate-400 uppercase tracking-wide">
                <th className="px-5 py-3 font-medium">Event</th>
                <th className="px-5 py-3 font-medium">Timestamp</th>
              </tr>
            </thead>
            <tbody>
              {myEvents.length === 0 && (
                <tr><td colSpan="2" className="px-5 py-8 text-center text-slate-400 text-sm">No activity recorded yet.</td></tr>
              )}
              {myEvents.map((e, i) => (
                <tr key={i} className="border-t border-slate-100 dark:border-slate-700/50">
                  <td className="px-5 py-3 font-medium">
                    <span className={e.type === 'ENTRY' ? 'text-emerald-600' : 'text-rose-600'}>{e.type}</span>
                  </td>
                  <td className="px-5 py-3 text-slate-500 dark:text-slate-400 text-xs">{e.timestamp}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}

export default MyProfilePage
