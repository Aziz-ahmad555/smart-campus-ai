import { useNavigate } from 'react-router-dom'
import { ScanFace, Users, Bell, Activity, ArrowRight, ShieldCheck, Zap, ExternalLink } from 'lucide-react'

function LandingPage() {
  const navigate = useNavigate()

  const features = [
    { icon: ScanFace, title: 'Real-Time Face Recognition', desc: 'DeepFace-powered identity matching with sub-2-second inference latency, even on CPU-only hardware.' },
    { icon: Users, title: 'Entry & Exit Tracking', desc: 'Persistent multi-object tracking via ByteTrack assigns stable IDs across frames for accurate occupancy logging.' },
    { icon: Bell, title: 'Crowd & Anomaly Alerts', desc: 'Threshold-based crowd detection and unknown-person flagging, pushed instantly via WebSockets.' },
    { icon: Activity, title: 'Live Analytics Dashboard', desc: 'Real-time occupancy, traffic trends, and recognition history in a production-grade interface.' },
  ]

  const stats = [
    { value: '0%', label: 'False Acceptance Rate' },
    { value: '100%', label: 'Low-Light Accuracy' },
    { value: '<1.3s', label: 'Avg. Recognition Latency' },
    { value: '3', label: 'Pipeline Stages Benchmarked' },
  ]

  return (
    <div className="min-h-screen bg-slate-950 text-white">
      <nav className="flex items-center justify-between px-8 py-6 max-w-7xl mx-auto">
        <div className="flex items-center gap-2">
          <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-blue-500 to-emerald-400 flex items-center justify-center font-bold">
            S
          </div>
          <span className="font-bold text-lg">Sentra</span>
        </div>
        <a href="https://github.com/Aziz-ahmad555/smart-campus-ai" target="_blank" rel="noreferrer" className="flex items-center gap-2 text-sm text-slate-400 hover:text-white transition-colors">
          <ExternalLink size={18} />
          View on GitHub
        </a>
      </nav>

      <section className="max-w-5xl mx-auto text-center px-8 pt-20 pb-24">
        <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-slate-900 border border-slate-800 text-xs text-slate-400 mb-6">
          <Zap size={12} className="text-emerald-400" />
          AI-Powered Perception Pipeline
        </div>
        <h1 className="text-5xl font-bold leading-tight mb-6">
          Intelligent Campus Surveillance,
          <br />
          <span className="bg-gradient-to-r from-blue-400 to-emerald-400 bg-clip-text text-transparent">
            Built for Real-Time Access Control
          </span>
        </h1>
        <p className="text-slate-400 text-lg max-w-2xl mx-auto mb-10">
          A full-stack AI perception system combining YOLOv8 detection, DeepFace recognition,
          and real-time tracking to identify, log, and monitor campus access — end to end.
        </p>
        <button onClick={() => navigate('/dashboard')} className="inline-flex items-center gap-2 px-6 py-3 rounded-lg bg-white text-slate-950 font-semibold hover:bg-slate-200 transition-colors">
          Launch Live Dashboard
          <ArrowRight size={18} />
        </button>
      </section>

      <section className="border-y border-slate-800 bg-slate-900/50">
        <div className="max-w-5xl mx-auto grid grid-cols-4 divide-x divide-slate-800">
          {stats.map((s, i) => (
            <div key={i} className="text-center py-8 px-4">
              <p className="text-3xl font-bold text-white">{s.value}</p>
              <p className="text-xs text-slate-500 mt-1">{s.label}</p>
            </div>
          ))}
        </div>
      </section>

      <section className="max-w-6xl mx-auto px-8 py-24">
        <div className="text-center mb-16">
          <h2 className="text-3xl font-bold mb-3">A Complete Perception Pipeline</h2>
          <p className="text-slate-400">Detection to Recognition to Tracking to Alerts to Dashboard</p>
        </div>
        <div className="grid grid-cols-2 gap-6">
          {features.map((f, i) => (
            <div key={i} className="p-6 rounded-xl bg-slate-900 border border-slate-800 hover:border-slate-700 transition-colors">
              <div className="w-10 h-10 rounded-lg bg-slate-800 flex items-center justify-center mb-4">
                <f.icon size={20} className="text-emerald-400" />
              </div>
              <h3 className="font-semibold mb-2">{f.title}</h3>
              <p className="text-sm text-slate-400">{f.desc}</p>
            </div>
          ))}
        </div>
      </section>

      <section className="max-w-4xl mx-auto px-8 pb-24 text-center">
        <div className="flex items-center justify-center gap-2 text-slate-500 text-sm">
          <ShieldCheck size={16} />
          Evaluated for accuracy, latency, and robustness across 5 real-world conditions
        </div>
      </section>

      <footer className="border-t border-slate-800 py-8 text-center text-xs text-slate-600">
        Built by Aziz Ahmad - Final Year Project
      </footer>
    </div>
  )
}

export default LandingPage
