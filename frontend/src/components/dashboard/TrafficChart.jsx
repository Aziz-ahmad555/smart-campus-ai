import { useMemo } from 'react'
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend } from 'recharts'
import { Activity } from 'lucide-react'
import { Card, CardHeader } from '../ui/Card'
import { EmptyState } from '../ui/States'
import { parseTime } from '../../lib/format'
import { useTheme } from '../../lib/theme'

const BUCKET_MINUTES = 5
const BUCKETS = 12 // one hour

// Entries and exits per 5-minute window for the hour up to the latest event.
function bucketize(events) {
  const times = events
    .filter((e) => e.type === 'ENTRY' || e.type === 'EXIT')
    .map((e) => ({ type: e.type, t: parseTime(e.timestamp) }))
    .filter((e) => e.t)
  if (!times.length) return []
  const latest = Math.max(...times.map((e) => e.t.getTime()))
  const size = BUCKET_MINUTES * 60000
  const end = Math.floor(latest / size) * size + size
  const start = end - BUCKETS * size
  const rows = Array.from({ length: BUCKETS }, (_, i) => {
    const at = new Date(start + i * size)
    return { time: at.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }), Entries: 0, Exits: 0 }
  })
  for (const e of times) {
    const i = Math.floor((e.t.getTime() - start) / size)
    if (i >= 0 && i < BUCKETS) rows[i][e.type === 'ENTRY' ? 'Entries' : 'Exits'] += 1
  }
  return rows
}

export default function TrafficChart({ events }) {
  const { theme } = useTheme()
  const data = useMemo(() => bucketize(events), [events])
  const dark = theme === 'dark'
  const axis = dark ? '#64748b' : '#94a3b8'

  return (
    <Card className="flex flex-col">
      <CardHeader icon={Activity} title="Foot traffic" description={`Entries and exits per ${BUCKET_MINUTES} minutes, last hour of activity`} />
      <div className="flex-1 px-3 pb-4 pt-4">
        {data.length === 0 ? (
          <EmptyState icon={Activity} title="No traffic yet" description="Entries and exits will be charted here as people are tracked." />
        ) : (
          <ResponsiveContainer width="100%" height={260}>
            <BarChart data={data} barGap={2} margin={{ top: 4, right: 8, left: -16, bottom: 0 }}>
              <CartesianGrid vertical={false} stroke={dark ? '#1e293b' : '#e2e8f0'} />
              <XAxis dataKey="time" tick={{ fontSize: 11, fill: axis }} axisLine={false} tickLine={false} interval="preserveStartEnd" />
              <YAxis tick={{ fontSize: 11, fill: axis }} axisLine={false} tickLine={false} allowDecimals={false} />
              <Tooltip
                cursor={{ fill: dark ? 'rgba(148,163,184,0.08)' : 'rgba(148,163,184,0.15)' }}
                contentStyle={{
                  borderRadius: 10,
                  border: `1px solid ${dark ? '#1e293b' : '#e2e8f0'}`,
                  background: dark ? '#0f172a' : '#fff',
                  fontSize: 12,
                  boxShadow: '0 8px 24px rgba(15,23,42,0.12)',
                }}
                labelStyle={{ color: dark ? '#e2e8f0' : '#0f172a', fontWeight: 600 }}
              />
              <Legend
                iconType="circle"
                iconSize={8}
                wrapperStyle={{ fontSize: 12, paddingTop: 8 }}
                formatter={(value) => <span style={{ color: dark ? '#cbd5e1' : '#475569' }}>{value}</span>}
              />
              <Bar dataKey="Entries" fill="#2563eb" radius={[4, 4, 0, 0]} maxBarSize={18} />
              <Bar dataKey="Exits" fill={dark ? '#475569' : '#cbd5e1'} radius={[4, 4, 0, 0]} maxBarSize={18} />
            </BarChart>
          </ResponsiveContainer>
        )}
      </div>
    </Card>
  )
}
