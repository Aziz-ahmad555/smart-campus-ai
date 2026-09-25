export function Card({ className = '', children, ...props }) {
  return (
    <div
      className={`rounded-xl border border-slate-200 bg-white shadow-sm shadow-slate-900/[0.03] dark:border-slate-800 dark:bg-slate-900 ${className}`}
      {...props}
    >
      {children}
    </div>
  )
}

export function CardHeader({ title, description, icon: Icon, actions, className = '' }) {
  return (
    <div className={`flex items-start justify-between gap-4 border-b border-slate-100 px-5 py-4 dark:border-slate-800 ${className}`}>
      <div className="flex min-w-0 items-start gap-3">
        {Icon && (
          <div className="mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-slate-100 text-slate-500 dark:bg-slate-800 dark:text-slate-400">
            <Icon size={16} aria-hidden="true" />
          </div>
        )}
        <div className="min-w-0">
          <h3 className="text-sm font-semibold text-slate-900 dark:text-white">{title}</h3>
          {description && <p className="mt-0.5 text-xs text-slate-500 dark:text-slate-400">{description}</p>}
        </div>
      </div>
      {actions && <div className="flex shrink-0 items-center gap-2">{actions}</div>}
    </div>
  )
}
