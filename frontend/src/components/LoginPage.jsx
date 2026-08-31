import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { LogIn, Fingerprint } from 'lucide-react'
import { startAuthentication } from '@simplewebauthn/browser'

function LoginPage() {
  const navigate = useNavigate()
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState(null)
  const [loading, setLoading] = useState(false)

  const redirectByRole = (role) => {
    if (role === 'admin') navigate('/dashboard')
    else if (role === 'teacher') navigate('/my-class')
    else navigate('/my-profile')
  }

  const handleLogin = async (e) => {
    e.preventDefault()
    setError(null)
    setLoading(true)
    try {
      const res = await fetch('http://localhost:8000/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username, password }),
      })
      if (!res.ok) {
        const err = await res.json()
        throw new Error(err.detail || 'Login failed')
      }
      const data = await res.json()
      localStorage.setItem('sentra_token', data.token)
      localStorage.setItem('sentra_user', JSON.stringify(data.user))
      redirectByRole(data.user.role)
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  const handleFingerprintLogin = async () => {
    if (!username) {
      setError('Enter your username first, then tap "Sign in with Fingerprint".')
      return
    }
    setError(null)
    setLoading(true)
    try {
      const beginRes = await fetch('http://localhost:8000/webauthn/login/begin?username=' + encodeURIComponent(username), { method: 'POST' })
      if (!beginRes.ok) {
        const err = await beginRes.json()
        throw new Error(err.detail || 'No fingerprint registered for this user')
      }
      const beginData = await beginRes.json()
      const options = JSON.parse(beginData.options)

      const credential = await startAuthentication({ optionsJSON: options })

      const completeRes = await fetch('http://localhost:8000/webauthn/login/complete', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username, credential }),
      })
      if (!completeRes.ok) {
        const err = await completeRes.json()
        throw new Error(err.detail || 'Fingerprint authentication failed')
      }
      const data = await completeRes.json()
      localStorage.setItem('sentra_token', data.token)
      localStorage.setItem('sentra_user', JSON.stringify(data.user))
      redirectByRole(data.user.role)
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen bg-slate-950 flex items-center justify-center px-4">
      <div className="w-full max-w-sm">
        <div className="flex items-center gap-2 justify-center mb-8">
          <div className="w-10 h-10 rounded-lg bg-gradient-to-br from-blue-500 to-emerald-400 flex items-center justify-center font-bold text-white text-lg">
            S
          </div>
          <div>
            <h1 className="font-bold text-xl text-white leading-tight">Sentra</h1>
            <p className="text-xs text-slate-400">Campus Intelligence</p>
          </div>
        </div>

        <form onSubmit={handleLogin} className="bg-slate-900 border border-slate-800 rounded-xl p-6">
          <h2 className="text-white font-semibold mb-4">Sign in</h2>

          {error && (
            <div className="mb-4 p-3 rounded-lg bg-rose-900/20 border border-rose-800 text-rose-400 text-sm">
              {error}
            </div>
          )}

          <div className="mb-4">
            <label className="text-xs text-slate-400 mb-1 block">Username</label>
            <input
              type="text"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              className="w-full px-3 py-2 rounded-lg bg-slate-800 border border-slate-700 text-white text-sm focus:outline-none focus:border-blue-500"
              placeholder="Enter your username"
              required
            />
          </div>

          <div className="mb-4">
            <label className="text-xs text-slate-400 mb-1 block">Password</label>
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="w-full px-3 py-2 rounded-lg bg-slate-800 border border-slate-700 text-white text-sm focus:outline-none focus:border-blue-500"
              placeholder="Enter your password"
              required
            />
          </div>

          <button
            type="submit"
            disabled={loading}
            className="w-full flex items-center justify-center gap-2 px-4 py-2.5 rounded-lg bg-white text-slate-950 font-semibold text-sm hover:bg-slate-200 transition-colors disabled:opacity-50 mb-3"
          >
            <LogIn size={16} />
            {loading ? 'Signing in...' : 'Sign in'}
          </button>

          <div className="flex items-center gap-2 my-3">
            <div className="flex-1 h-px bg-slate-800"></div>
            <span className="text-xs text-slate-500">OR</span>
            <div className="flex-1 h-px bg-slate-800"></div>
          </div>

          <button
            type="button"
            onClick={handleFingerprintLogin}
            disabled={loading}
            className="w-full flex items-center justify-center gap-2 px-4 py-2.5 rounded-lg bg-slate-800 text-white font-semibold text-sm hover:bg-slate-700 transition-colors disabled:opacity-50"
          >
            <Fingerprint size={16} />
            Sign in with Fingerprint
          </button>
        </form>
      </div>
    </div>
  )
}

export default LoginPage
