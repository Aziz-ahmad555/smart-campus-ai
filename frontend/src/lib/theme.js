import { useCallback, useSyncExternalStore } from 'react'

// Light/dark theme, remembered across pages and visits. Defaults to the OS
// preference until the user picks one.
const KEY = 'sentra_theme'
const listeners = new Set()

function preferred() {
  const saved = localStorage.getItem(KEY)
  if (saved === 'light' || saved === 'dark') return saved
  return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light'
}

function apply(theme) {
  document.documentElement.classList.toggle('dark', theme === 'dark')
}

export function initTheme() {
  apply(preferred())
}

function subscribe(listener) {
  listeners.add(listener)
  return () => listeners.delete(listener)
}

export function useTheme() {
  const theme = useSyncExternalStore(subscribe, preferred)
  const setTheme = useCallback((next) => {
    localStorage.setItem(KEY, next)
    apply(next)
    listeners.forEach((l) => l())
  }, [])
  const toggle = useCallback(() => setTheme(preferred() === 'dark' ? 'light' : 'dark'), [setTheme])
  return { theme, setTheme, toggle }
}
