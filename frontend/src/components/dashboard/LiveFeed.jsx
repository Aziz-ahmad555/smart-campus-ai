import { useEffect, useState } from 'react'
import { Video, VideoOff, RotateCw } from 'lucide-react'
import { Card, CardHeader } from '../ui/Card'
import { Badge } from '../ui/Badge'
import { Button } from '../ui/Button'
import { streamUrl } from '../../lib/api'

export default function LiveFeed() {
  const [src, setSrc] = useState(null)
  const [failed, setFailed] = useState(false)
  const [attempt, setAttempt] = useState(0)

  // Each attempt gets a fresh single-use ticket for the MJPEG stream.
  useEffect(() => {
    let cancelled = false
    streamUrl('video', '/video-feed')
      .then((url) => !cancelled && setSrc(url))
      .catch(() => !cancelled && setFailed(true))
    return () => {
      cancelled = true
    }
  }, [attempt])

  const retry = () => {
    setSrc(null)
    setFailed(false)
    setAttempt((a) => a + 1)
  }

  return (
    <Card className="flex flex-col overflow-hidden">
      <CardHeader
        icon={Video}
        title="Camera feed"
        description="Detection and tracking overlays from the inference engine"
        actions={failed ? <Badge tone="danger" dot>Offline</Badge> : <Badge tone={src ? 'success' : 'neutral'} dot>{src ? 'Live' : 'Connecting…'}</Badge>}
      />
      <div className="relative flex aspect-video items-center justify-center bg-slate-950">
        {failed ? (
          <div className="flex flex-col items-center gap-3 px-6 text-center">
            <VideoOff size={28} className="text-slate-500" aria-hidden="true" />
            <div>
              <p className="text-sm font-medium text-slate-200">Video stream unavailable</p>
              <p className="mt-1 text-xs text-slate-400">The backend or camera isn&apos;t running.</p>
            </div>
            <Button variant="secondary" size="sm" icon={RotateCw} onClick={retry}>
              Try again
            </Button>
          </div>
        ) : (
          src && (
            <img
              key={src}
              src={src}
              alt="Live camera feed with detection overlays"
              className="h-full w-full object-contain"
              onError={() => setFailed(true)}
            />
          )
        )}
      </div>
    </Card>
  )
}
