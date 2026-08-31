import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { LogOut, Users, Clock } from 'lucide-react'

function MyClassPage() {
  const navigate = useNavigate()
  const [classData, setClassData] = useState({ class_name: null, students: [] })
  const [events, setEvents] = useState([])
  const userJson = localStorage.getItem('sentra_user')
  const user = userJson ? JSON.parse(userJson) : null

  useEffect(() => {
    if (!user) return
    fetch('http://localhost:8000/secure/my-class-roster?token=' + localStorage.getItem('sentra_token'))
      .then((res) => res.json())
      .then((data) => setClassData(data))
      .catch(() => {})

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

  const studentNames = classData.students.map((s) => s.name)
  const classEvents = events.filter((e) => studentNames.some((name) => e.label && e.label.includes(name)))

  return (
    <div className="min-h-screen bg-slate-50 dark:bg-slate-900 p-8">
      <div className="max-w-3xl mx-auto">
        <div className="flex items-center justify-between mb-8">
          <div>
            <h2 className="text-2xl font-bold text-slate-900 dark:text-white">My Class</h2>
            <p className="text-sm text-slate-500 dark:text-slate-400 mt-1">
              {classData.class_name ? classData.class_name : 'No class assigned'} — {user ? user.full_name : ''}
            </p>
          </div>
          <button onClick={handleLogout} className="flex items-center gap-2 px-4 py-2 rounded-lg bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-200 text-sm font-medium hover:bg-slate-200 dark:hover:bg-slate-700 transition-colors">
            <LogOut size={16} />
            Log Out
          </button>
        </div>

        <div className="bg-white dark:bg-slate-800 rounded-xl border border-slate-200 dark:border-slate-700 shadow-sm overflow-hidden mb-6">
          <div className="p-5 border-b border-slate-200 dark:border-slate-700">
            <h3 className="font-semibold text-slate-900 dark:text-white flex items-center gap-2">
              <Users size={16} />
              Class Roster ({classData.students.length})
            </h3>
          </div>
          <table className="w-full text-sm">
            <thead className="bg-slate-50 dark:bg-slate-900/50">
              <tr className="text-left text-xs text-slate-500 dark:text-slate-400 uppercase tracking-wide">
                <th className="px-5 py-3 font-medium">Name</th>
                <th className="px-5 py-3 font-medium">Roll Number</th>
              </tr>
            </thead>
            <tbody>
              {classData.students.length === 0 && (
                <tr><td colSpan="2" className="px-5 py-8 text-center text-slate-400 text-sm">No students assigned to this class yet.</td></tr>
              )}
              {classData.students.map((s) => (
                <tr key={s.id} className="border-t border-slate-100 dark:border-slate-700/50">
                  <td className="px-5 py-3 text-slate-900 dark:text-white font-medium">{s.name}</td>
                  <td className="px-5 py-3 text-slate-600 dark:text-slate-300">{s.roll_number}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        <div className="bg-white dark:bg-slate-800 rounded-xl border border-slate-200 dark:border-slate-700 shadow-sm overflow-hidden">
          <div className="p-5 border-b border-slate-200 dark:border-slate-700">
            <h3 className="font-semibold text-slate-900 dark:text-white flex items-center gap-2">
              <Clock size={16} />
              Recent Class Activity
            </h3>
          </div>
          <table className="w-full text-sm">
            <thead className="bg-slate-50 dark:bg-slate-900/50">
              <tr className="text-left text-xs text-slate-500 dark:text-slate-400 uppercase tracking-wide">
                <th className="px-5 py-3 font-medium">Event</th>
                <th className="px-5 py-3 font-medium">Student</th>
                <th className="px-5 py-3 font-medium">Timestamp</th>
              </tr>
            </thead>
            <tbody>
              {classEvents.length === 0 && (
                <tr><td colSpan="3" className="px-5 py-8 text-center text-slate-400 text-sm">No activity recorded for this class yet.</td></tr>
              )}
              {classEvents.map((e, i) => (
                <tr key={i} className="border-t border-slate-100 dark:border-slate-700/50">
                  <td className="px-5 py-3 font-medium">
                    <span className={e.type === 'ENTRY' ? 'text-emerald-600' : 'text-rose-600'}>{e.type}</span>
                  </td>
                  <td className="px-5 py-3 text-slate-600 dark:text-slate-300">{e.label}</td>
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

export default MyClassPage

