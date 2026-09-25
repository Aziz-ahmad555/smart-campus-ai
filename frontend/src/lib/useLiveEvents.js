import { useCallback, useEffect, useState } from 'react'
import { api, streamUrl } from './api'
import { IDENTIFYING_TTL_MS, trackIdentifying } from './events'

// Recognition events: the newest page of history from the database, then
// live pushes over the WebSocket (reconnecting with backoff and a fresh
// stream ticket). loadOlder() pages further back. Newest first. `identifying`
// holds the people currently being identified (live only, not stored).
const PAGE_SIZE = 100

// Append stored events, skipping any already shown (the same page can be
// fetched twice, e.g. when an effect re-runs). Live events have no id yet.
function mergeHistory(current, incoming) {
  const ids = new Set(current.map((e) => e.id).filter((id) => id != null))
  return [...current, ...incoming.filter((e) => !ids.has(e.id))]
}

export function useLiveEvents() {
  const [events, setEvents] = useState([])
  const [identifying, setIdentifying] = useState({})
  const [status, setStatus] = useState('connecting') // connecting | live | offline
  const [error, setError] = useState(null)
  const [nextBefore, setNextBefore] = useState(null)
  const [loadingOlder, setLoadingOlder] = useState(false)

  const loadOlder = useCallback(async () => {
    if (!nextBefore || loadingOlder) return
    setLoadingOlder(true)
    try {
      const data = await api('/events', { auth: true, params: { limit: PAGE_SIZE, before: nextBefore } })
      setEvents((prev) => mergeHistory(prev, data.events))
      setNextBefore(data.next_before)
    } catch (err) {
      setError(err.message)
    } finally {
      setLoadingOlder(false)
    }
  }, [nextBefore, loadingOlder])

  useEffect(() => {
    let ws
    let retry
    let attempts = 0
    let closed = false

    api('/events', { auth: true, params: { limit: PAGE_SIZE } })
      .then((data) => {
        setEvents((live) => mergeHistory(live, data.events))     // keeps live events that arrived first
        setNextBefore(data.next_before)
      })
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
          setIdentifying((prev) => trackIdentifying(prev, event))
          if (event.type !== 'IDENTIFYING') setEvents((prev) => [event, ...prev])
        } catch {
          // ignore malformed messages
        }
      }
      ws.onclose = scheduleRetry
    }
    connect()
    const prune = setInterval(() => setIdentifying((prev) => trackIdentifying(prev, null)), IDENTIFYING_TTL_MS / 4)

    return () => {
      closed = true
      clearTimeout(retry)
      clearInterval(prune)
      ws?.close()
    }
  }, [])

  return { events, identifying: Object.values(identifying), status, error, loadOlder, hasOlder: Boolean(nextBefore), loadingOlder }
}
