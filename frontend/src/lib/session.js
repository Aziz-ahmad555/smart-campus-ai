// Browser-side session: the token, when it expires, and the signed-in user,
// as returned by /login or /webauthn/login/complete.
const TOKEN_KEY = 'sentra_token'
const USER_KEY = 'sentra_user'
const EXPIRES_KEY = 'sentra_expires_at'

export function getToken() {
  return localStorage.getItem(TOKEN_KEY)
}

export function getUser() {
  try {
    return JSON.parse(localStorage.getItem(USER_KEY) || 'null')
  } catch {
    return null
  }
}

// Seconds since the epoch, as sent by the backend.
export function isExpired() {
  const expiresAt = Number(localStorage.getItem(EXPIRES_KEY))
  return Boolean(expiresAt) && Date.now() / 1000 >= expiresAt
}

export function hasSession() {
  return Boolean(getToken() && getUser()) && !isExpired()
}

export function saveSession({ token, user, expires_at: expiresAt }) {
  localStorage.setItem(TOKEN_KEY, token)
  localStorage.setItem(USER_KEY, JSON.stringify(user))
  if (expiresAt) localStorage.setItem(EXPIRES_KEY, String(expiresAt))
  else localStorage.removeItem(EXPIRES_KEY)
}

export function clearSession() {
  localStorage.removeItem(TOKEN_KEY)
  localStorage.removeItem(USER_KEY)
  localStorage.removeItem(EXPIRES_KEY)
}

// Called when the backend says the session is no longer valid.
export function endExpiredSession() {
  clearSession()
  if (window.location.pathname !== '/login') window.location.assign('/login?expired=1')
}

export function homePathFor(role) {
  if (role === 'teacher') return '/my-class'
  if (role === 'student') return '/my-profile'
  return '/dashboard'
}
