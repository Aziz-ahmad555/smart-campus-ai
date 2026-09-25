import { initials } from '../../lib/format'

const AVATAR_TONES = [
  'bg-blue-100 text-blue-700 dark:bg-blue-500/15 dark:text-blue-300',
  'bg-emerald-100 text-emerald-700 dark:bg-emerald-500/15 dark:text-emerald-300',
  'bg-violet-100 text-violet-700 dark:bg-violet-500/15 dark:text-violet-300',
  'bg-amber-100 text-amber-800 dark:bg-amber-500/15 dark:text-amber-300',
  'bg-rose-100 text-rose-700 dark:bg-rose-500/15 dark:text-rose-300',
  'bg-cyan-100 text-cyan-700 dark:bg-cyan-500/15 dark:text-cyan-300',
]

export function Avatar({ name, size = 'md' }) {
  const sizes = { sm: 'h-7 w-7 text-[11px]', md: 'h-9 w-9 text-xs', lg: 'h-14 w-14 text-lg' }
  const hash = [...(name || '')].reduce((h, ch) => (h * 31 + ch.charCodeAt(0)) >>> 0, 0)
  return (
    <span
      className={`inline-flex shrink-0 items-center justify-center rounded-full font-semibold ${sizes[size]} ${AVATAR_TONES[hash % AVATAR_TONES.length]}`}
      aria-hidden="true"
    >
      {initials(name)}
    </span>
  )
}

export function Logo({ size = 'md', subtitle = true, inverted = false }) {
  const box = size === 'lg' ? 'h-10 w-10 text-lg' : 'h-8 w-8 text-sm'
  return (
    <div className="flex items-center gap-2.5">
      <div className={`flex ${box} items-center justify-center rounded-lg bg-gradient-to-br from-blue-500 to-emerald-400 font-bold text-white shadow-sm`}>
        S
      </div>
      <div>
        <p className={`font-semibold leading-tight tracking-tight ${size === 'lg' ? 'text-xl' : 'text-base'} ${inverted ? 'text-white' : 'text-slate-900 dark:text-white'}`}>
          Sentra
        </p>
        {subtitle && <p className="text-xs text-slate-500 dark:text-slate-400">Campus Intelligence</p>}
      </div>
    </div>
  )
}

export function PageHeader({ title, description, actions }) {
  return (
    <div className="mb-6 flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight text-slate-900 dark:text-white">{title}</h1>
        {description && <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">{description}</p>}
      </div>
      {actions && <div className="flex flex-wrap items-center gap-2">{actions}</div>}
    </div>
  )
}

export function StatCard({ label, value, hint, icon: Icon, tone = 'blue', loading = false }) {
  const tones = {
    blue: 'bg-blue-50 text-blue-600 dark:bg-blue-500/10 dark:text-blue-400',
    emerald: 'bg-emerald-50 text-emerald-600 dark:bg-emerald-500/10 dark:text-emerald-400',
    violet: 'bg-violet-50 text-violet-600 dark:bg-violet-500/10 dark:text-violet-400',
    amber: 'bg-amber-50 text-amber-600 dark:bg-amber-500/10 dark:text-amber-400',
    rose: 'bg-rose-50 text-rose-600 dark:bg-rose-500/10 dark:text-rose-400',
    slate: 'bg-slate-100 text-slate-600 dark:bg-slate-800 dark:text-slate-300',
  }
  return (
    <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm shadow-slate-900/[0.03] dark:border-slate-800 dark:bg-slate-900">
      <div className="flex items-center justify-between">
        <p className="text-sm font-medium text-slate-500 dark:text-slate-400">{label}</p>
        {Icon && (
          <div className={`flex h-9 w-9 items-center justify-center rounded-lg ${tones[tone]}`}>
            <Icon size={18} aria-hidden="true" />
          </div>
        )}
      </div>
      {loading ? (
        <div className="mt-2 h-8 w-16 animate-pulse rounded-md bg-slate-200/70 dark:bg-slate-800" />
      ) : (
        <p className="mt-1 text-3xl font-semibold tracking-tight text-slate-900 tabular-nums dark:text-white">{value}</p>
      )}
      {hint && <p className="mt-1 text-xs text-slate-500 dark:text-slate-400">{hint}</p>}
    </div>
  )
}

// Segmented control, e.g. for table filters.
export function Tabs({ value, onChange, options, label }) {
  return (
    <div role="tablist" aria-label={label} className="inline-flex rounded-lg bg-slate-100 p-1 dark:bg-slate-800/70">
      {options.map((o) => (
        <button
          key={o.value}
          role="tab"
          aria-selected={value === o.value}
          onClick={() => onChange(o.value)}
          className={`rounded-md px-3 py-1.5 text-xs font-medium transition-colors ${
            value === o.value
              ? 'bg-white text-slate-900 shadow-sm dark:bg-slate-900 dark:text-white'
              : 'text-slate-500 hover:text-slate-800 dark:text-slate-400 dark:hover:text-slate-200'
          }`}
        >
          {o.label}
          {o.count != null && <span className="ml-1.5 tabular-nums text-slate-400">{o.count}</span>}
        </button>
      ))}
    </div>
  )
}
