import { useCallback, useEffect, useLayoutEffect, useRef, useState } from 'react'
import { api } from './api'

// Loads `path` on mount (and every `interval` ms if given), with loading and
// error state. `select` picks the part of the response the page needs.
export function useApi(path, { auth = false, interval, select = (d) => d, initial = null } = {}) {
  const [data, setData] = useState(initial)
  const [error, setError] = useState(null)
  const [loading, setLoading] = useState(true)
  const selectRef = useRef(select)
  useLayoutEffect(() => {
    selectRef.current = select
  })

  const load = useCallback(async () => {
    try {
      const result = await api(path, { auth })
      setData(selectRef.current(result))
      setError(null)
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }, [path, auth])

  useEffect(() => {
    load()
    if (!interval) return undefined
    const id = setInterval(load, interval)
    return () => clearInterval(id)
  }, [load, interval])

  return { data, error, loading, reload: load }
}
