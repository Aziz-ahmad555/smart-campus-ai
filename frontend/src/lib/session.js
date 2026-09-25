// Browser-side session: the token and the signed-in user, as returned by
// /login or /webauthn/login/complete. Storage keys are unchanged.
const TOKEN_KEY = 'sentra_token'
const USER_KEY = 'sentra_user'

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

export function saveSession({ token, user }) {
  localStorage.setItem(TOKEN_KEY, token)
  localStorage.setItem(USER_KEY, JSON.stringify(user))
}

export function clearSession() {
  localStorage.removeItem(TOKEN_KEY)
  localStorage.removeItem(USER_KEY)
}

export function homePathFor(role) {
  if (role === 'teacher') return '/my-class'
  if (role === 'student') return '/my-profile'
  return '/dashboard'
}
