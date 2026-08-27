import { useState, useEffect } from 'react'
import './App.css'

function App() {
  const [events, setEvents] = useState([])
  const [error, setError] = useState(null)

  useEffect(() => {
    const fetchEvents = () => {
      fetch('http://localhost:8000/events')
        .then((res) => res.json())
        .then((data) => {
          setEvents(data.events.slice().reverse()) // newest first
          setError(null)
        })
        .catch((err) => {
          setError('Could not connect to backend. Is the API server running?')
        })
    }

    fetchEvents() // fetch immediately on load
    const interval = setInterval(fetchEvents, 2000) // then poll every 2 seconds

    return () => clearInterval(interval) // cleanup on unmount
  }, [])

  return (
    <div style={{ fontFamily: 'sans-serif', maxWidth: '800px', margin: '0 auto', padding: '2rem' }}>
      <h1>Smart Campus AI — Live Dashboard</h1>
      <p>Real-time entry/exit events from the surveillance system.</p>

      {error && <p style={{ color: 'red' }}>{error}</p>}

      {!error && events.length === 0 && <p>No events yet. Waiting for detections...</p>}

      <table style={{ width: '100%', borderCollapse: 'collapse', marginTop: '1rem' }}>
        <thead>
          <tr style={{ borderBottom: '2px solid #333', textAlign: 'left' }}>
            <th style={{ padding: '8px' }}>Type</th>
            <th style={{ padding: '8px' }}>Track ID</th>
            <th style={{ padding: '8px' }}>Person</th>
            <th style={{ padding: '8px' }}>Timestamp</th>
          </tr>
        </thead>
        <tbody>
          {events.map((event, index) => (
            <tr key={index} style={{ borderBottom: '1px solid #ddd' }}>
              <td style={{
                padding: '8px',
                color: event.type === 'ENTRY' ? 'green' : 'red',
                fontWeight: 'bold'
              }}>
                {event.type}
              </td>
              <td style={{ padding: '8px' }}>{event.track_id}</td>
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
