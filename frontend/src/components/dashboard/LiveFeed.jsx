import { useState } from 'react'
import { Video, VideoOff, RotateCw } from 'lucide-react'
import { Card, CardHeader } from '../ui/Card'
import { Badge } from '../ui/Badge'
import { Button } from '../ui/Button'
import { apiUrl } from '../../lib/api'

export default function LiveFeed() {
  const [failed, setFailed] = useState(false)
  const [attempt, setAttempt] = useState(0)

  return (
    <Card className="flex flex-col overflow-hidden">
      <CardHeader
        icon={Video}
        title="Camera feed"
        description="Detection and tracking overlays from the inference engine"
        actions={failed ? <Badge tone="danger" dot>Offline</Badge> : <Badge tone="success" dot>Live</Badge>}
      />
      <div className="relative flex aspect-video items-center justify-center bg-slate-950">
        {!failed ? (
          <img
            key={attempt}
            src={apiUrl('/video-feed', { params: { t: attempt } })}
            alt="Live camera feed with detection overlays"
            className="h-full w-full object-contain"
            onError={() => setFailed(true)}
          />
        ) : (
          <div className="flex flex-col items-center gap-3 px-6 text-center">
            <VideoOff size={28} className="text-slate-500" aria-hidden="true" />
            <div>
              <p className="text-sm font-medium text-slate-200">Video stream unavailable</p>
              <p className="mt-1 text-xs text-slate-400">The backend or camera isn&apos;t running.</p>
            </div>
            <Button
              variant="secondary"
              size="sm"
              icon={RotateCw}
              onClick={() => {
                setFailed(false)
                setAttempt((a) => a + 1)
              }}
            >
              Try again
            </Button>
          </div>
        )}
      </div>
    </Card>
  )
}
