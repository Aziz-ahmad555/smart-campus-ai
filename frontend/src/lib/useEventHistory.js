import { useCallback, useEffect, useRef, useState } from 'react'
import { api } from './api'

// Paginated event history (newest first) from an endpoint that returns
// { events, next_before, ...rest }. The first page refreshes every
// `interval` ms; older pages are fetched on demand with loadOlder().
export function useEventHistory(path, { interval, pageSize = 50 } = {}) {
  const [first, setFirst] = useState(null)        // the whole first-page response
  const [older, setOlder] = useState([])          // events from later pages
  const [nextBefore, setNextBefore] = useState(null)
  const [error, setError] = useState(null)
  const [loading, setLoading] = useState(true)
  const [loadingOlder, setLoadingOlder] = useState(false)
  const olderLoaded = useRef(false)

  const load = useCallback(async () => {
    try {
      const data = await api(path, { auth: true, params: { limit: pageSize } })
      setFirst(data)
      if (!olderLoaded.current) setNextBefore(data.next_before)
      setError(null)
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }, [path, pageSize])

  useEffect(() => {
    // load() only sets state after the request resolves, not synchronously.
    // oxlint-disable-next-line react/set-state-in-effect
    load()
    if (!interval) return undefined
    const id = setInterval(load, interval)
    return () => clearInterval(id)
  }, [load, interval])

  const loadOlder = useCallback(async () => {
    if (!nextBefore || loadingOlder) return
    setLoadingOlder(true)
    try {
      const data = await api(path, { auth: true, params: { limit: pageSize, before: nextBefore } })
      olderLoaded.current = true
      setOlder((prev) => [...prev, ...data.events])
      setNextBefore(data.next_before)
    } catch (err) {
      setError(err.message)
    } finally {
      setLoadingOlder(false)
    }
  }, [path, pageSize, nextBefore, loadingOlder])

  // First page + older pages, without duplicates.
  const seen = new Set()
  const events = [...(first?.events || []), ...older].filter((e) => !seen.has(e.id) && seen.add(e.id))

  return { data: first, events, error, loading, reload: load, loadOlder, hasOlder: Boolean(nextBefore), loadingOlder }
}
