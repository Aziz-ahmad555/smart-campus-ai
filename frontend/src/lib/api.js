// Single place that knows where the backend lives and how requests are
// authenticated. Set VITE_API_URL to point the UI at another backend.
import { getToken } from './session'

export const API_URL = (import.meta.env.VITE_API_URL || 'http://localhost:8000').replace(/\/$/, '')
export const WS_URL = API_URL.replace(/^http/, 'ws')

export class ApiError extends Error {
  constructor(message, status) {
    super(message)
    this.status = status
  }
}

// The backend takes the session token as a `token` query parameter.
export function apiUrl(path, { auth = false, params = {} } = {}) {
  const url = new URL(API_URL + path)
  if (auth) url.searchParams.set('token', getToken() || '')
  for (const [key, value] of Object.entries(params)) url.searchParams.set(key, value)
  return url.toString()
}

export async function api(path, { method = 'GET', body, auth = false, params } = {}) {
  let res
  try {
    res = await fetch(apiUrl(path, { auth, params }), {
      method,
      headers: body !== undefined ? { 'Content-Type': 'application/json' } : undefined,
      body: body !== undefined ? JSON.stringify(body) : undefined,
    })
  } catch {
    throw new ApiError('Cannot reach the server. Check that the backend is running.', 0)
  }
  const data = await res.json().catch(() => ({}))
  if (!res.ok) {
    const detail = typeof data.detail === 'string' ? data.detail : null
    throw new ApiError(detail || `Request failed (${res.status})`, res.status)
  }
  return data
}
