import { Video, VideoOff } from 'lucide-react'
import { useState } from 'react'

function LiveFeed() {
  const [streamError, setStreamError] = useState(false)

  return (
    <div className="bg-white dark:bg-slate-800 rounded-xl border border-slate-200 dark:border-slate-700 shadow-sm overflow-hidden">
      <div className="p-5 border-b border-slate-200 dark:border-slate-700 flex items-center justify-between">
        <div>
          <h3 className="font-semibold text-slate-900 dark:text-white">Live Camera Feed</h3>
          <p className="text-xs text-slate-500 dark:text-slate-400 mt-0.5">
            Real-time inference output — detection and tracking overlays
          </p>
        </div>
        {streamError ? <VideoOff size={18} className="text-rose-500" /> : <Video size={18} className="text-emerald-500" />}
      </div>
      <div className="bg-slate-900 flex items-center justify-center" style={{ minHeight: '280px' }}>
        {!streamError ? (
          <img
            src="http://localhost:8000/video-feed"
            alt="Live camera feed"
            className="w-full h-auto"
            onError={() => setStreamError(true)}
          />
        ) : (
          <p className="text-slate-500 text-sm py-16">Video stream unavailable. Is the backend running?</p>
        )}
      </div>
    </div>
  )
}

export default LiveFeed
