import { Loader2 } from 'lucide-react'

const VARIANTS = {
  primary: 'bg-blue-600 text-white shadow-sm hover:bg-blue-700 active:bg-blue-800 disabled:hover:bg-blue-600',
  secondary:
    'bg-white text-slate-700 border border-slate-200 shadow-sm hover:bg-slate-50 dark:bg-slate-900 dark:text-slate-200 dark:border-slate-700 dark:hover:bg-slate-800',
  ghost: 'text-slate-600 hover:bg-slate-100 hover:text-slate-900 dark:text-slate-300 dark:hover:bg-slate-800 dark:hover:text-white',
  danger: 'bg-rose-600 text-white shadow-sm hover:bg-rose-700 active:bg-rose-800',
}

const SIZES = {
  sm: 'h-8 px-3 text-xs gap-1.5',
  md: 'h-9 px-4 text-sm gap-2',
  lg: 'h-11 px-5 text-sm gap-2',
}

export function Button({ variant = 'primary', size = 'md', icon: Icon, loading = false, className = '', children, ...props }) {
  return (
    <button
      type="button"
      disabled={loading || props.disabled}
      className={`inline-flex items-center justify-center rounded-lg font-medium whitespace-nowrap transition-colors disabled:cursor-not-allowed disabled:opacity-60 ${VARIANTS[variant]} ${SIZES[size]} ${className}`}
      {...props}
    >
      {loading ? <Loader2 size={16} className="animate-spin" /> : Icon && <Icon size={16} aria-hidden="true" />}
      {children}
    </button>
  )
}

// Square icon-only button; `label` is required so it's never an unlabeled control.
export function IconButton({ icon: Icon, label, tone = 'default', className = '', ...props }) {
  const tones = {
    default: 'text-slate-400 hover:text-slate-700 hover:bg-slate-100 dark:hover:text-slate-200 dark:hover:bg-slate-800',
    danger: 'text-slate-400 hover:text-rose-600 hover:bg-rose-50 dark:hover:text-rose-400 dark:hover:bg-rose-500/10',
  }
  return (
    <button
      type="button"
      aria-label={label}
      title={label}
      className={`inline-flex h-8 w-8 items-center justify-center rounded-lg transition-colors ${tones[tone]} ${className}`}
      {...props}
    >
      <Icon size={16} aria-hidden="true" />
    </button>
  )
}
