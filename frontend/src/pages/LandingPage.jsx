import { Link } from 'react-router-dom'
import {
  ScanFace, Users, Bell, LayoutDashboard, ArrowRight, Camera, Scan, Database, Route, Radio, ShieldCheck, UserCheck, Fingerprint,
} from 'lucide-react'
import { Logo } from '../components/ui/Misc'

const GITHUB = 'https://github.com/Aziz-ahmad555/smart-campus-ai'

const FEATURES = [
  {
    icon: ScanFace,
    title: 'Face recognition',
    text: 'MTCNN face detection with Facenet512 embeddings, confirmed by a vote over several frames before a name is logged.',
  },
  {
    icon: Users,
    title: 'Entry and exit tracking',
    text: 'ByteTrack keeps a stable ID for each person in view, so every entry and exit is logged with a timestamp.',
  },
  {
    icon: Bell,
    title: 'Crowd and fall alerts',
    text: 'Alerts when more people are in view than allowed, and when a tracked person may have fallen.',
  },
  {
    icon: LayoutDashboard,
    title: 'Live dashboard',
    text: 'Camera feed, foot traffic and an event log that update the moment the pipeline sees someone.',
  },
  {
    icon: UserCheck,
    title: 'Visitor management',
    text: 'Check visitors in with an allowed duration and see who has overstayed at a glance.',
  },
  {
    icon: Fingerprint,
    title: 'Role-based access',
    text: 'Separate views for admins, teachers and students, with fingerprint or Windows Hello sign-in.',
  },
]

// Measured results from the project's evaluation suite (see README).
const STATS = [
  { value: '86.7%', label: 'Recognition accuracy', note: '15 held-out test images' },
  { value: '0%', label: 'False acceptance rate', note: 'No stranger matched as a known person' },
  { value: '~7 FPS', label: 'Detection on CPU', note: 'Per pipeline stage, no GPU' },
  { value: '5', label: 'Conditions tested', note: 'Incl. low light, angles, occlusion' },
]

const PIPELINE = [
  { icon: Camera, label: 'Camera' },
  { icon: Scan, label: 'YOLOv8 detection' },
  { icon: ScanFace, label: 'Face recognition' },
  { icon: Database, label: 'Student lookup' },
  { icon: Route, label: 'ByteTrack tracking' },
  { icon: Radio, label: 'Live events' },
]

export default function LandingPage() {
  return (
    <div className="min-h-screen bg-slate-950 text-white">
      <header className="relative z-10 mx-auto flex max-w-7xl items-center justify-between px-6 py-5 lg:px-8">
        <Logo inverted subtitle={false} />
        <nav className="flex items-center gap-2">
          <a href={GITHUB} target="_blank" rel="noreferrer" className="hidden rounded-lg px-3 py-2 text-sm text-slate-400 transition-colors hover:text-white sm:block">
            GitHub
          </a>
          <Link to="/login" className="rounded-lg bg-white/10 px-4 py-2 text-sm font-medium text-white ring-1 ring-white/15 transition-colors hover:bg-white/15">
            Sign in
          </Link>
        </nav>
      </header>

      {/* Hero */}
      <section className="relative overflow-hidden">
        <div className="pointer-events-none absolute left-1/2 top-0 h-[480px] w-[900px] -translate-x-1/2 rounded-full bg-blue-600/20 blur-3xl" aria-hidden="true" />
        <div
          className="pointer-events-none absolute inset-0 opacity-[0.07] [background-image:linear-gradient(to_right,white_1px,transparent_1px),linear-gradient(to_bottom,white_1px,transparent_1px)] [background-size:48px_48px] [mask-image:radial-gradient(ellipse_at_top,black,transparent_70%)]"
          aria-hidden="true"
        />
        <div className="relative mx-auto max-w-4xl px-6 pb-20 pt-16 text-center sm:pt-24">
          <div className="mb-6 inline-flex items-center gap-2 rounded-full bg-white/5 px-3 py-1 text-xs text-slate-300 ring-1 ring-white/10">
            <span className="h-1.5 w-1.5 rounded-full bg-emerald-400" aria-hidden="true" />
            Real-time AI perception for campuses
          </div>
          <h1 className="text-4xl font-semibold leading-tight tracking-tight sm:text-6xl">
            Know who&apos;s on campus,{' '}
            <span className="bg-gradient-to-r from-blue-400 to-emerald-300 bg-clip-text text-transparent">the moment they arrive.</span>
          </h1>
          <p className="mx-auto mt-6 max-w-2xl text-base text-slate-400 sm:text-lg">
            Sentra combines YOLOv8 detection, face recognition and multi-object tracking to identify people,
            log every entry and exit, and raise alerts, all streamed to a live dashboard.
          </p>
          <div className="mt-10 flex flex-col items-center justify-center gap-3 sm:flex-row">
            <Link
              to="/login"
              className="inline-flex h-11 items-center gap-2 rounded-lg bg-white px-5 text-sm font-semibold text-slate-950 transition-colors hover:bg-slate-200"
            >
              Open the dashboard
              <ArrowRight size={16} aria-hidden="true" />
            </Link>
            <a
              href={GITHUB}
              target="_blank"
              rel="noreferrer"
              className="inline-flex h-11 items-center rounded-lg px-5 text-sm font-medium text-slate-300 ring-1 ring-white/15 transition-colors hover:bg-white/5 hover:text-white"
            >
              View the source
            </a>
          </div>
        </div>
      </section>

      {/* Measured results */}
      <section className="border-y border-white/10 bg-white/[0.02]">
        <div className="mx-auto grid max-w-6xl grid-cols-2 lg:grid-cols-4">
          {STATS.map((s, i) => (
            <div key={s.label} className={`px-6 py-8 text-center ${i % 2 ? 'border-l border-white/10' : ''} ${i >= 2 ? 'border-t border-white/10 lg:border-t-0' : ''} ${i === 2 ? 'lg:border-l' : ''}`}>
              <p className="text-3xl font-semibold tracking-tight tabular-nums">{s.value}</p>
              <p className="mt-1 text-sm text-slate-300">{s.label}</p>
              <p className="mt-0.5 text-xs text-slate-500">{s.note}</p>
            </div>
          ))}
        </div>
      </section>

      {/* Pipeline */}
      <section className="mx-auto max-w-6xl px-6 py-20 lg:px-8">
        <div className="mx-auto max-w-2xl text-center">
          <h2 className="text-3xl font-semibold tracking-tight">One pipeline, camera to dashboard</h2>
          <p className="mt-3 text-slate-400">Every frame goes through the same stages, and every result is traceable to what the camera saw.</p>
        </div>
        <ol className="mt-12 grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6">
          {PIPELINE.map((step, i) => (
            <li key={step.label} className="relative rounded-xl bg-white/[0.03] p-4 text-center ring-1 ring-white/10">
              <span className="absolute left-3 top-2 text-[11px] font-medium tabular-nums text-slate-600">{String(i + 1).padStart(2, '0')}</span>
              <step.icon size={22} className="mx-auto mb-2 text-emerald-400" aria-hidden="true" />
              <p className="text-sm text-slate-200">{step.label}</p>
            </li>
          ))}
        </ol>
      </section>

      {/* Features */}
      <section className="mx-auto max-w-6xl px-6 pb-24 lg:px-8">
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {FEATURES.map((f) => (
            <div key={f.title} className="rounded-xl bg-white/[0.03] p-6 ring-1 ring-white/10 transition-colors hover:bg-white/[0.05]">
              <div className="mb-4 flex h-10 w-10 items-center justify-center rounded-lg bg-emerald-400/10 ring-1 ring-emerald-400/20">
                <f.icon size={18} className="text-emerald-300" aria-hidden="true" />
              </div>
              <h3 className="font-medium">{f.title}</h3>
              <p className="mt-2 text-sm leading-relaxed text-slate-400">{f.text}</p>
            </div>
          ))}
        </div>
        <p className="mt-10 flex items-center justify-center gap-2 text-center text-sm text-slate-500">
          <ShieldCheck size={16} aria-hidden="true" />
          Evaluated for accuracy, latency and robustness. Recognition takes about 2.6 s per face on CPU.
        </p>
      </section>

      <footer className="border-t border-white/10">
        <div className="mx-auto flex max-w-6xl flex-col items-center justify-between gap-3 px-6 py-8 text-xs text-slate-500 sm:flex-row lg:px-8">
          <p>Sentra · Smart Campus AI</p>
          <p>Built by Aziz Ahmad · Final Year Project</p>
        </div>
      </footer>
    </div>
  )
}
