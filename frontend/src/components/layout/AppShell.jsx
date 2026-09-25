import { useState } from 'react'
import { NavLink, useNavigate } from 'react-router-dom'
import { startRegistration } from '@simplewebauthn/browser'
import {
  LayoutDashboard, GraduationCap, Briefcase, School, UserCheck, UserRound, Users, KeyRound,
  Fingerprint, Moon, Sun, LogOut, Menu, X,
} from 'lucide-react'
import { api } from '../../lib/api'
import { clearSession, getUser } from '../../lib/session'
import { useTheme } from '../../lib/theme'
import { Avatar, Logo } from '../ui/Misc'
import { useToast } from '../ui/Toast'

// Only pages that exist and that this role may open.
const NAV = {
  admin: [
    { section: 'Monitoring', items: [{ label: 'Live dashboard', icon: LayoutDashboard, to: '/dashboard' }] },
    {
      section: 'Directory',
      items: [
        { label: 'Students', icon: GraduationCap, to: '/students' },
        { label: 'Staff', icon: Briefcase, to: '/staff' },
        { label: 'Classes', icon: School, to: '/classes' },
        { label: 'Visitors', icon: UserCheck, to: '/visitors' },
      ],
    },
    { section: 'Administration', items: [{ label: 'Accounts', icon: KeyRound, to: '/users' }] },
  ],
  teacher: [{ section: 'Teaching', items: [{ label: 'My class', icon: Users, to: '/my-class' }] }],
  student: [{ section: 'Account', items: [{ label: 'My profile', icon: UserRound, to: '/my-profile' }] }],
}

const ROLE_LABEL = { admin: 'Administrator', teacher: 'Teacher', student: 'Student' }

function SidebarAction({ icon: Icon, children, tone = 'default', ...props }) {
  const tones = {
    default: 'text-slate-600 hover:bg-slate-100 hover:text-slate-900 dark:text-slate-400 dark:hover:bg-slate-800 dark:hover:text-white',
    danger: 'text-slate-600 hover:bg-rose-50 hover:text-rose-700 dark:text-slate-400 dark:hover:bg-rose-500/10 dark:hover:text-rose-300',
  }
  return (
    <button type="button" className={`flex w-full items-center gap-3 rounded-lg px-3 py-2 text-sm transition-colors ${tones[tone]}`} {...props}>
      <Icon size={17} aria-hidden="true" />
      {children}
    </button>
  )
}

function Sidebar({ onNavigate }) {
  const navigate = useNavigate()
  const toast = useToast()
  const { theme, toggle } = useTheme()
  const user = getUser()
  const sections = NAV[user?.role] || []
  const [registering, setRegistering] = useState(false)

  const signOut = async () => {
    try {
      await api('/logout', { method: 'POST', auth: true })
    } catch {
      // Signing out locally still works if the server is unreachable.
    }
    clearSession()
    navigate('/login')
  }

  // Registers this device's fingerprint / Windows Hello (WebAuthn) for sign-in.
  const registerFingerprint = async () => {
    setRegistering(true)
    try {
      const begin = await api('/webauthn/register/begin', { method: 'POST', auth: true })
      const credential = await startRegistration({ optionsJSON: JSON.parse(begin.options) })
      await api('/webauthn/register/complete', { method: 'POST', auth: true, body: { credential } })
      toast.success('Fingerprint sign-in is set up for this device.')
    } catch (err) {
      toast.error(err.name === 'NotAllowedError' ? 'Fingerprint setup was cancelled.' : `Fingerprint setup failed: ${err.message}`)
    } finally {
      setRegistering(false)
    }
  }

  return (
    <div className="flex h-full flex-col overflow-y-auto">
      <div className="px-5 py-5">
        <Logo />
      </div>

      <nav className="flex-1 space-y-6 px-3 py-2" aria-label="Main">
        {sections.map((s) => (
          <div key={s.section}>
            <p className="px-3 pb-2 text-[11px] font-semibold uppercase tracking-wider text-slate-400 dark:text-slate-500">{s.section}</p>
            <div className="space-y-0.5">
              {s.items.map((item) => (
                <NavLink
                  key={item.to}
                  to={item.to}
                  onClick={onNavigate}
                  className={({ isActive }) =>
                    `flex items-center gap-3 rounded-lg px-3 py-2 text-sm transition-colors ${
                      isActive
                        ? 'bg-blue-50 font-medium text-blue-700 dark:bg-blue-500/10 dark:text-blue-300'
                        : 'text-slate-600 hover:bg-slate-100 hover:text-slate-900 dark:text-slate-400 dark:hover:bg-slate-800 dark:hover:text-white'
                    }`
                  }
                >
                  <item.icon size={17} aria-hidden="true" />
                  {item.label}
                </NavLink>
              ))}
            </div>
          </div>
        ))}
      </nav>

      <div className="space-y-0.5 border-t border-slate-200 p-3 dark:border-slate-800">
        <SidebarAction icon={Fingerprint} onClick={registerFingerprint} disabled={registering}>
          {registering ? 'Waiting for device…' : 'Set up fingerprint sign-in'}
        </SidebarAction>
        <SidebarAction icon={theme === 'dark' ? Sun : Moon} onClick={toggle}>
          {theme === 'dark' ? 'Light mode' : 'Dark mode'}
        </SidebarAction>
        <SidebarAction icon={LogOut} tone="danger" onClick={signOut}>Sign out</SidebarAction>

        {user && (
          <div className="mt-2 flex items-center gap-3 rounded-lg bg-slate-50 px-3 py-2.5 dark:bg-slate-800/60">
            <Avatar name={user.full_name || user.username} size="sm" />
            <div className="min-w-0">
              <p className="truncate text-sm font-medium text-slate-900 dark:text-white">{user.full_name || user.username}</p>
              <p className="truncate text-xs text-slate-500 dark:text-slate-400">{ROLE_LABEL[user.role] || user.role}</p>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}

export default function AppShell({ children }) {
  const [open, setOpen] = useState(false)   // mobile drawer; closed on navigation via onNavigate

  return (
    <div className="min-h-screen">
      {/* Desktop sidebar */}
      <aside className="fixed inset-y-0 left-0 z-30 hidden w-64 border-r border-slate-200 bg-white lg:block dark:border-slate-800 dark:bg-slate-900">
        <Sidebar />
      </aside>

      {/* Mobile top bar + drawer */}
      <header className="sticky top-0 z-30 flex h-14 items-center justify-between border-b border-slate-200 bg-white/90 px-4 backdrop-blur lg:hidden dark:border-slate-800 dark:bg-slate-900/90">
        <Logo subtitle={false} />
        <button
          type="button"
          onClick={() => setOpen(true)}
          aria-label="Open menu"
          className="rounded-lg p-2 text-slate-600 hover:bg-slate-100 dark:text-slate-300 dark:hover:bg-slate-800"
        >
          <Menu size={20} />
        </button>
      </header>
      {open && (
        <div className="fixed inset-0 z-40 lg:hidden">
          <div className="absolute inset-0 animate-fade-in bg-slate-950/50" onClick={() => setOpen(false)} aria-hidden="true" />
          <aside className="absolute inset-y-0 left-0 w-72 animate-slide-up bg-white shadow-xl dark:bg-slate-900">
            <button
              type="button"
              onClick={() => setOpen(false)}
              aria-label="Close menu"
              className="absolute right-3 top-4 rounded-lg p-2 text-slate-500 hover:bg-slate-100 dark:hover:bg-slate-800"
            >
              <X size={18} />
            </button>
            <Sidebar onNavigate={() => setOpen(false)} />
          </aside>
        </div>
      )}

      <main className="lg:pl-64">
        <div className="mx-auto max-w-7xl px-4 py-6 sm:px-6 lg:px-8 lg:py-8">{children}</div>
      </main>
    </div>
  )
}
