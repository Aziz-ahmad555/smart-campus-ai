import { LayoutDashboard, Users, AlertTriangle, Activity, Moon, Sun, LogOut, ScanFace } from 'lucide-react'
import { useNavigate, useLocation } from 'react-router-dom'
import { startRegistration } from '@simplewebauthn/browser'

function Sidebar({ darkMode, setDarkMode }) {
  const navigate = useNavigate()
  const location = useLocation()

  const userJson = localStorage.getItem('sentra_user')
  const user = userJson ? JSON.parse(userJson) : null

  const navItems = [
    { label: 'Dashboard', icon: LayoutDashboard, path: '/dashboard' },
    { label: 'Students', icon: Users, path: '/students' },
    { label: 'Staff', icon: Users, path: '/staff' },
    { label: 'Classes', icon: LayoutDashboard, path: '/classes' },
    { label: 'Visitors', icon: Users, path: '/visitors' },
    { label: 'Alerts', icon: AlertTriangle, path: '/dashboard' },
    { label: 'Analytics', icon: Activity, path: '/dashboard' },
  ]

  const handleLogout = async () => {
    const token = localStorage.getItem('sentra_token')
    try {
      await fetch('http://localhost:8000/logout?token=' + token, { method: 'POST' })
    } catch (e) {}
    localStorage.removeItem('sentra_token')
    localStorage.removeItem('sentra_user')
    navigate('/login')
  }

  const handleRegisterScanFace = async () => {
    const token = localStorage.getItem('sentra_token')
    try {
      const beginRes = await fetch('http://localhost:8000/webauthn/register/begin?token=' + token, { method: 'POST' })
      if (!beginRes.ok) throw new Error('Could not start ScanFace registration')
      const beginData = await beginRes.json()
      const options = JSON.parse(beginData.options)

      const credential = await startRegistration({ optionsJSON: options })

      const completeRes = await fetch('http://localhost:8000/webauthn/register/complete?token=' + token, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ credential }),
      })
      if (!completeRes.ok) throw new Error('ScanFace registration failed')

      alert('ScanFace registered successfully! You can now sign in using your ScanFace.')
    } catch (e) {
      alert('ScanFace registration failed: ' + e.message)
    }
  }

  return (
    <div className="w-64 h-screen bg-slate-900 text-slate-100 flex flex-col fixed left-0 top-0 overflow-y-auto">
      <div className="p-6 border-b border-slate-800">
        <div className="flex items-center gap-2">
          <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-blue-500 to-emerald-400 flex items-center justify-center font-bold text-white">
            S
          </div>
          <div>
            <h1 className="font-bold text-lg leading-tight">Sentra</h1>
            <p className="text-xs text-slate-400">Campus Intelligence</p>
          </div>
        </div>
      </div>

      <nav className="flex-1 p-4 space-y-1">
        {navItems.map((item) => {
          const isActive = location.pathname === item.path
          const btnClass = 'w-full flex items-center gap-3 px-4 py-2.5 rounded-lg text-sm transition-colors ' +
            (isActive ? 'bg-slate-800 text-white font-medium' : 'text-slate-400 hover:bg-slate-800 hover:text-white')
          return (
            <button
              key={item.label}
              onClick={() => navigate(item.path)}
              className={btnClass}
            >
              <item.icon size={18} />
              {item.label}
            </button>
          )
        })}
      </nav>

      <div className="p-4 border-t border-slate-800 space-y-1">
        {user && (
          <div className="px-4 py-2 mb-1">
            <p className="text-sm text-white font-medium">{user.full_name || user.username}</p>
            <p className="text-xs text-slate-500 capitalize">{user.role}</p>
          </div>
        )}
        <button
          onClick={handleRegisterScanFace}
          className="w-full flex items-center gap-3 px-4 py-2.5 rounded-lg text-slate-400 hover:bg-slate-800 hover:text-white transition-colors text-sm"
        >
          <ScanFace size={18} />
          Register ScanFace
        </button>
        <button
          onClick={() => setDarkMode(!darkMode)}
          className="w-full flex items-center gap-3 px-4 py-2.5 rounded-lg text-slate-400 hover:bg-slate-800 hover:text-white transition-colors text-sm"
        >
          {darkMode ? <Sun size={18} /> : <Moon size={18} />}
          {darkMode ? 'Light Mode' : 'Dark Mode'}
        </button>
        <button
          onClick={handleLogout}
          className="w-full flex items-center gap-3 px-4 py-2.5 rounded-lg text-slate-400 hover:bg-rose-900/30 hover:text-rose-400 transition-colors text-sm"
        >
          <LogOut size={18} />
          Log Out
        </button>
      </div>
    </div>
  )
}

export default Sidebar


