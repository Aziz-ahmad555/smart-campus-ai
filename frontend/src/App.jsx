import { useState, useEffect, useMemo } from 'react'
import { Users, LogIn, AlertTriangle, ScanFace } from 'lucide-react'
import Sidebar from './components/Sidebar'
import StatCard from './components/StatCard'
import TrafficChart from './components/TrafficChart'
import EventsTable from './components/EventsTable'

function App() {
  const [events, setEvents] = useState([])
  const [connected, setConnected] = useState(false)
  const [error, setError] = useState(null)
  const [darkMode, setDarkMode] = useState(false)

  useEffect(() => {
    fetch('http://localhost:8000/events')
      .then((res) => res.json())
      .then((data) => setEvents(data.events.slice().reverse()))
      .catch(() => setError('Could not load initial events.'))

    const ws = new WebSocket('ws://localhost:8000/ws/events')

    ws.onopen = () => {
      setConnected(true)
      setError(null)
    }
    ws.onmessage = (message) => {
      const newEvent = JSON.parse(message.data)
      setEvents((prev) => [newEvent, ...prev])
    }
    ws.onerror = () => setError('WebSocket connection error. Is the backend running?')
    ws.onclose = () => setConnected(false)

    return () => ws.close()
  }, [])

  useEffect(() => {
    if (darkMode) {
      document.documentElement.classList.add('dark')
    } else {
      document.documentElement.classList.remove('dark')
    }
  }, [darkMode])

  // Derived stats
  const occupancy = useMemo(() => {
    const inside = new Set()
    // process oldest to newest to correctly track who is currently inside
    const chronological = events.slice().reverse()
    for (const e of chronological) {
      if (e.type === 'ENTRY') inside.add(e.track_id)
      if (e.type === 'EXIT') inside.delete(e.track_id)
    }
    return inside.size
  }, [events])

  const totalEntries = useMemo(
    () => events.filter((e) => e.type === 'ENTRY').length,
    [events]
  )

  const activeAlerts = useMemo(
    () => events.filter((e) => e.type === 'CROWD_ALERT').length,
    [events]
  )

  const uniqueIdentities = useMemo(() => {
    const names = new Set(
      events.filter((e) => e.type === 'ENTRY' && e.label !== 'Unknown').map((e) => e.label)
    )
    return names.size
  }, [events])

  // Build traffic chart data — bucket entries/exits by minute
  const chartData = useMemo(() => {
    const buckets = {}
    const chronological = events.slice().reverse()
    for (const e of chronological) {
      if (e.type !== 'ENTRY' && e.type !== 'EXIT') continue
      const minute = e.timestamp.slice(11, 16) // "HH:MM"
      buckets[minute] = (buckets[minute] || 0) + 1
    }
    return Object.entries(buckets).map(([time, count]) => ({ time, count }))
  }, [events])

  return (
    <div className="min-h-screen bg-slate-50 dark:bg-slate-900 transition-colors">
      <Sidebar darkMode={darkMode} setDarkMode={setDarkMode} />

      <div className="ml-64 p-8">
        <div className="flex items-center justify-between mb-8">
          <div>
            <h2 className="text-2xl font-bold text-slate-900 dark:text-white">
              Live Surveillance Dashboard
            </h2>
            <p className="text-sm text-slate-500 dark:text-slate-400 mt-1">
              Real-time perception pipeline — detection, recognition, and access tracking
            </p>
          </div>
          <div className="flex items-center gap-2 px-3 py-1.5 rounded-full bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700">
            <span className={'w-2 h-2 rounded-full ' + (connected ? 'bg-emerald-500' : 'bg-rose-500')}></span>
            <span className="text-xs font-medium text-slate-600 dark:text-slate-300">
              {connected ? 'Inference Engine Online' : 'Disconnected'}
            </span>
          </div>
        </div>

        {error && (
          <div className="mb-6 p-4 rounded-lg bg-rose-50 dark:bg-rose-900/20 border border-rose-200 dark:border-rose-800 text-rose-700 dark:text-rose-400 text-sm">
            {error}
          </div>
        )}

        <div className="grid grid-cols-4 gap-4 mb-6">
          <StatCard
            label="Current Occupancy"
            value={occupancy}
            icon={Users}
            trend="People currently in frame"
            accentColor="bg-blue-500"
          />
          <StatCard
            label="Total Entries"
            value={totalEntries}
            icon={LogIn}
            trend="Since session start"
            accentColor="bg-emerald-500"
          />
          <StatCard
            label="Identities Recognized"
            value={uniqueIdentities}
            icon={ScanFace}
            trend="Unique known faces"
            accentColor="bg-violet-500"
          />
          <StatCard
            label="Active Alerts"
            value={activeAlerts}
            icon={AlertTriangle}
            trend="Crowd threshold events"
            accentColor="bg-amber-500"
          />
        </div>

        <div className="grid grid-cols-1 gap-6 mb-6">
          <TrafficChart data={chartData} />
        </div>

        <EventsTable events={events} />
      </div>
    </div>
  )
}

export default App
