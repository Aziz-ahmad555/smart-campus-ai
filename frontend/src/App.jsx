import { useState, useEffect, useRef } from 'react'
import './App.css'

function App() {
  const [events, setEvents] = useState([])
  const [connected, setConnected] = useState(false)
  const [error, setError] = useState(null)
  const wsRef = useRef(null)

  useEffect(() => {
    fetch('http://localhost:8000/events')
      .then((res) => res.json())
      .then((data) => setEvents(data.events.slice().reverse()))
      .catch(() => setError('Could not load initial events.'))

    const ws = new WebSocket('ws://localhost:8000/ws/events')
    wsRef.current = ws

    ws.onopen = () => {
      setConnected(true)
      setError(null)
    }

    ws.onmessage = (message) => {
      const newEvent = JSON.parse(message.data)
      setEvents((prev) => [newEvent, ...prev])
    }

    ws.onerror = () => {
      setError('WebSocket connection error. Is the backend running?')
    }

    ws.onclose = () => {
      setConnected(false)
    }

    return () => {
      ws.close()
    }
  }, [])

  const getTypeColor = (type) => {
    if (type === 'ENTRY') return 'green'
    if (type === 'EXIT') return 'red'
    if (type === 'CROWD_ALERT') return 'orange'
    return 'black'
  }

  return (
    <div style={{ fontFamily: 'sans-serif', maxWidth: '800px', margin: '0 auto', padding: '2rem' }}>
      <h1>Smart Campus AI — Live Dashboard</h1>
      <p style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
        Real-time entry/exit events from the surveillance system.
        <span style={{ display: 'inline-flex', alignItems: 'center', gap: '4px', color: connected ? 'green' : 'red', fontWeight: 'bold' }}>
          <span style={{
            display: 'inline-block',
            width: '10px',
            height: '10px',
            borderRadius: '50%',
            backgroundColor: connected ? 'green' : 'red'
          }}></span>
          {connected ? 'Live' : 'Disconnected'}
        </span>
      </p>

      {error && <p style={{ color: 'red' }}>{error}</p>}
      {!error && events.length === 0 && <p>No events yet. Waiting for detections...</p>}

      <table style={{ width: '100%', borderCollapse: 'collapse', marginTop: '1rem' }}>
        <thead>
          <tr style={{ borderBottom: '2px solid #333', textAlign: 'left' }}>
            <th style={{ padding: '8px' }}>Type</th>
            <th style={{ padding: '8px' }}>Track ID</th>
            <th style={{ padding: '8px' }}>Person / Details</th>
            <th style={{ padding: '8px' }}>Timestamp</th>
          </tr>
        </thead>
        <tbody>
          {events.map((event, index) => (
            <tr key={index} style={{
              borderBottom: '1px solid #ddd',
              backgroundColor: event.type === 'CROWD_ALERT' ? '#fff3e0' : 'transparent'
            }}>
              <td style={{
                padding: '8px',
                color: getTypeColor(event.type),
                fontWeight: 'bold'
              }}>
                {event.type === 'CROWD_ALERT' ? '⚠ CROWD ALERT' : event.type}
              </td>
              <td style={{ padding: '8px' }}>{event.track_id ?? '—'}</td>
              <td style={{ padding: '8px' }}>{event.label}</td>
              <td style={{ padding: '8px' }}>{event.timestamp}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

export default App
