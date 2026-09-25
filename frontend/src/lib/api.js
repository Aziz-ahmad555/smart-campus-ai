// Single place that knows where the backend lives and how requests are
// authenticated. Set VITE_API_URL to point the UI at another backend.
import { endExpiredSession, getToken } from './session'

export const API_URL = (import.meta.env.VITE_API_URL || 'http://localhost:8000').replace(/\/$/, '')
export const WS_URL = API_URL.replace(/^http/, 'ws')

export class ApiError extends Error {
  constructor(message, status) {
    super(message)
    this.status = status
  }
}

export function apiUrl(path, { params = {} } = {}) {
  const url = new URL(API_URL + path)
  for (const [key, value] of Object.entries(params)) url.searchParams.set(key, value)
  return url.toString()
}

// The session token goes in the Authorization header, never in the URL.
export async function api(path, { method = 'GET', body, auth = false, params } = {}) {
  const headers = {}
  if (body !== undefined) headers['Content-Type'] = 'application/json'
  if (auth) headers.Authorization = `Bearer ${getToken() || ''}`

  let res
  try {
    res = await fetch(apiUrl(path, { params }), {
      method,
      headers,
      body: body !== undefined ? JSON.stringify(body) : undefined,
    })
  } catch {
    throw new ApiError('Cannot reach the server. Check that the backend is running.', 0)
  }
  const data = await res.json().catch(() => ({}))
  if (!res.ok) {
    if (auth && res.status === 401) endExpiredSession()
    const detail = typeof data.detail === 'string' ? data.detail : null
    throw new ApiError(detail || `Request failed (${res.status})`, res.status)
  }
  return data
}

// The camera feed (<img>) and the event WebSocket can't send the header, so
// they use a short-lived, single-use ticket from the backend instead.
export async function streamUrl(purpose, path) {
  const { ticket } = await api('/stream-ticket', { method: 'POST', auth: true, params: { purpose } })
  return `${purpose === 'events' ? WS_URL : API_URL}${path}?ticket=${encodeURIComponent(ticket)}`
}
