import { useEffect, useState } from 'react'
import { api, streamUrl } from './api'

// Recognition events: the backend's recent log, then live pushes over the
// WebSocket. Reconnects with backoff (and a fresh stream ticket) if the
// connection drops. Returns events newest first.
export function useLiveEvents() {
  const [events, setEvents] = useState([])
  const [status, setStatus] = useState('connecting') // connecting | live | offline
  const [error, setError] = useState(null)

  useEffect(() => {
    let ws
    let retry
    let attempts = 0
    let closed = false

    api('/events', { auth: true })
      .then((data) => setEvents(data.events.slice().reverse()))
      .catch((err) => setError(err.message))

    const scheduleRetry = () => {
      if (closed) return
      setStatus('offline')
      attempts += 1
      retry = setTimeout(connect, Math.min(1000 * 2 ** attempts, 15000))
    }

    const connect = async () => {
      let url
      try {
        url = await streamUrl('events', '/ws/events')
      } catch {
        scheduleRetry()
        return
      }
      if (closed) return
      ws = new WebSocket(url)
      ws.onopen = () => {
        attempts = 0
        setStatus('live')
        setError(null)
      }
      ws.onmessage = (message) => {
        try {
          const event = JSON.parse(message.data)
          setEvents((prev) => [event, ...prev].slice(0, 500))
        } catch {
          // ignore malformed messages
        }
      }
      ws.onclose = scheduleRetry
    }
    connect()

    return () => {
      closed = true
      clearTimeout(retry)
      ws?.close()
    }
  }, [])

  return { events, status, error }
}
