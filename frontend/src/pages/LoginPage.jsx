import { useState } from 'react'
import { Link, Navigate, useNavigate } from 'react-router-dom'
import { Fingerprint, Eye, EyeOff, ScanFace, ShieldCheck, Radio, ArrowLeft } from 'lucide-react'
import { startAuthentication } from '@simplewebauthn/browser'
import { Button } from '../components/ui/Button'
import { Input } from '../components/ui/Field'
import { Logo } from '../components/ui/Misc'
import { ErrorBanner } from '../components/ui/States'
import { api } from '../lib/api'
import { getToken, getUser, homePathFor, saveSession } from '../lib/session'

const HIGHLIGHTS = [
  { icon: ScanFace, title: 'Face recognition', text: 'Known students and staff identified on entry.' },
  { icon: Radio, title: 'Live event stream', text: 'Entries, exits and alerts pushed in real time.' },
  { icon: ShieldCheck, title: 'Role-based access', text: 'Admins, teachers and students each see only their own views.' },
]

export default function LoginPage() {
  const navigate = useNavigate()
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [showPassword, setShowPassword] = useState(false)
  const [error, setError] = useState(null)
  const [loading, setLoading] = useState(null) // null | 'password' | 'fingerprint'

  const existing = getUser()
  if (getToken() && existing) return <Navigate to={homePathFor(existing.role)} replace />

  const finish = (data) => {
    saveSession(data)
    navigate(homePathFor(data.user.role))
  }

  const signIn = async (e) => {
    e.preventDefault()
    setError(null)
    setLoading('password')
    try {
      finish(await api('/login', { method: 'POST', body: { username, password } }))
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(null)
    }
  }

  const signInWithFingerprint = async () => {
    if (!username.trim()) {
      setError('Enter your username first, then use fingerprint sign-in.')
      return
    }
    setError(null)
    setLoading('fingerprint')
    try {
      const begin = await api('/webauthn/login/begin', { method: 'POST', params: { username } })
      const credential = await startAuthentication({ optionsJSON: JSON.parse(begin.options) })
      finish(await api('/webauthn/login/complete', { method: 'POST', body: { username, credential } }))
    } catch (err) {
      setError(err.name === 'NotAllowedError' ? 'Fingerprint sign-in was cancelled.' : err.message)
    } finally {
      setLoading(null)
    }
  }

  return (
    <div className="grid min-h-screen bg-white lg:grid-cols-2 dark:bg-slate-950">
      {/* Brand panel */}
      <div className="relative hidden overflow-hidden bg-slate-950 p-12 lg:flex lg:flex-col lg:justify-between">
        <div className="pointer-events-none absolute -left-32 -top-32 h-96 w-96 rounded-full bg-blue-600/25 blur-3xl" aria-hidden="true" />
        <div className="pointer-events-none absolute -bottom-40 right-0 h-96 w-96 rounded-full bg-emerald-500/15 blur-3xl" aria-hidden="true" />
        <div className="relative">
          <Link to="/" aria-label="Sentra home"><Logo inverted /></Link>
        </div>
        <div className="relative max-w-md">
          <h2 className="text-3xl font-semibold tracking-tight text-white">Campus access, understood in real time.</h2>
          <p className="mt-3 text-slate-400">Detection, recognition and tracking in one command view for your campus.</p>
          <ul className="mt-10 space-y-6">
            {HIGHLIGHTS.map((h) => (
              <li key={h.title} className="flex gap-4">
                <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-white/5 ring-1 ring-white/10">
                  <h.icon size={18} className="text-emerald-400" aria-hidden="true" />
                </div>
                <div>
                  <p className="font-medium text-white">{h.title}</p>
                  <p className="text-sm text-slate-400">{h.text}</p>
                </div>
              </li>
            ))}
          </ul>
        </div>
        <p className="relative text-xs text-slate-500">Smart Campus AI · Final Year Project</p>
      </div>

      {/* Form */}
      <div className="flex flex-col px-6 py-8 sm:px-12">
        <Link to="/" className="inline-flex items-center gap-1.5 self-start text-sm text-slate-500 hover:text-slate-900 dark:text-slate-400 dark:hover:text-white">
          <ArrowLeft size={16} aria-hidden="true" />
          Back to home
        </Link>
        <div className="mx-auto flex w-full max-w-sm flex-1 flex-col justify-center py-10">
          <div className="mb-8 lg:hidden"><Logo /></div>
          <h1 className="text-2xl font-semibold tracking-tight text-slate-900 dark:text-white">Sign in</h1>
          <p className="mt-1.5 text-sm text-slate-500 dark:text-slate-400">Use your campus account to continue.</p>

          <form onSubmit={signIn} className="mt-8 space-y-4">
            <ErrorBanner message={error} />
            <Input
              label="Username"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              autoComplete="username"
              autoFocus
              required
            />
            <div className="relative">
              <Input
                label="Password"
                type={showPassword ? 'text' : 'password'}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                autoComplete="current-password"
                required
                className="pr-10"
              />
              <button
                type="button"
                onClick={() => setShowPassword((s) => !s)}
                aria-label={showPassword ? 'Hide password' : 'Show password'}
                className="absolute right-2 top-[34px] rounded-md p-1.5 text-slate-400 hover:text-slate-700 dark:hover:text-slate-200"
              >
                {showPassword ? <EyeOff size={16} /> : <Eye size={16} />}
              </button>
            </div>
            <Button type="submit" size="lg" className="w-full" loading={loading === 'password'} disabled={loading !== null}>
              Sign in
            </Button>
          </form>

          <div className="my-6 flex items-center gap-3 text-xs text-slate-400">
            <div className="h-px flex-1 bg-slate-200 dark:bg-slate-800" />
            or
            <div className="h-px flex-1 bg-slate-200 dark:bg-slate-800" />
          </div>

          <Button
            variant="secondary"
            size="lg"
            icon={Fingerprint}
            className="w-full"
            onClick={signInWithFingerprint}
            loading={loading === 'fingerprint'}
            disabled={loading !== null}
          >
            Sign in with fingerprint
          </Button>
          <p className="mt-3 text-center text-xs text-slate-500 dark:text-slate-400">
            Works with a fingerprint reader or Windows Hello set up from your account.
          </p>
        </div>
      </div>
    </div>
  )
}
