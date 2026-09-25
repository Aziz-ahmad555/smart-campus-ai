import { AlertCircle, RotateCw } from 'lucide-react'
import { Button } from './Button'

export function EmptyState({ icon: Icon, title, description, action, className = '' }) {
  return (
    <div className={`flex flex-col items-center justify-center px-6 py-14 text-center ${className}`}>
      {Icon && (
        <div className="mb-4 flex h-12 w-12 items-center justify-center rounded-full bg-slate-100 text-slate-400 dark:bg-slate-800 dark:text-slate-500">
          <Icon size={22} aria-hidden="true" />
        </div>
      )}
      <p className="text-sm font-semibold text-slate-900 dark:text-white">{title}</p>
      {description && <p className="mt-1 max-w-sm text-sm text-slate-500 dark:text-slate-400">{description}</p>}
      {action && <div className="mt-5">{action}</div>}
    </div>
  )
}

export function ErrorBanner({ message, onRetry, className = '' }) {
  if (!message) return null
  return (
    <div
      role="alert"
      className={`flex items-center gap-3 rounded-xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-800 dark:border-rose-500/30 dark:bg-rose-500/10 dark:text-rose-200 ${className}`}
    >
      <AlertCircle size={18} className="shrink-0" aria-hidden="true" />
      <p className="flex-1">{message}</p>
      {onRetry && (
        <Button variant="ghost" size="sm" icon={RotateCw} onClick={onRetry} className="text-rose-800 hover:bg-rose-100 dark:text-rose-200 dark:hover:bg-rose-500/20">
          Retry
        </Button>
      )}
    </div>
  )
}

export function Skeleton({ className = '' }) {
  return <div className={`animate-pulse rounded-md bg-slate-200/70 dark:bg-slate-800 ${className}`} />
}

export function SkeletonRows({ rows = 4, cols = 4 }) {
  return Array.from({ length: rows }, (_, r) => (
    <tr key={r} className="border-t border-slate-100 dark:border-slate-800">
      {Array.from({ length: cols }, (_, c) => (
        <td key={c} className="px-5 py-4">
          <Skeleton className={`h-4 ${c === 0 ? 'w-32' : 'w-20'}`} />
        </td>
      ))}
    </tr>
  ))
}
