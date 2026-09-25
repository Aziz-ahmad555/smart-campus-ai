import { useId } from 'react'

const CONTROL =
  'block w-full h-10 rounded-lg border border-slate-200 bg-white px-3 text-sm text-slate-900 shadow-sm placeholder:text-slate-400 ' +
  'transition-colors focus:border-blue-500 focus:outline-none focus:ring-4 focus:ring-blue-500/15 ' +
  'dark:border-slate-700 dark:bg-slate-950 dark:text-white dark:placeholder:text-slate-500 disabled:opacity-60'

// Label + control + hint/error, wired together with ids for screen readers.
function Field({ label, hint, error, required, children }) {
  const id = useId()
  const describedBy = error || hint ? `${id}-desc` : undefined
  return (
    <div>
      {label && (
        <label htmlFor={id} className="mb-1.5 block text-sm font-medium text-slate-700 dark:text-slate-300">
          {label}
          {required && <span className="ml-0.5 text-rose-500" aria-hidden="true">*</span>}
        </label>
      )}
      {children({ id, 'aria-describedby': describedBy, 'aria-invalid': error ? true : undefined, required })}
      {(error || hint) && (
        <p id={describedBy} className={`mt-1.5 text-xs ${error ? 'text-rose-600 dark:text-rose-400' : 'text-slate-500 dark:text-slate-400'}`}>
          {error || hint}
        </p>
      )}
    </div>
  )
}

export function Input({ label, hint, error, required, className = '', ...props }) {
  return (
    <Field label={label} hint={hint} error={error} required={required}>
      {(a11y) => <input className={`${CONTROL} ${className}`} {...a11y} {...props} />}
    </Field>
  )
}

export function Select({ label, hint, error, required, className = '', children, ...props }) {
  return (
    <Field label={label} hint={hint} error={error} required={required}>
      {(a11y) => (
        <select className={`${CONTROL} pr-8 ${className}`} {...a11y} {...props}>
          {children}
        </select>
      )}
    </Field>
  )
}

// Compact search box used above tables.
export function SearchInput({ value, onChange, placeholder = 'Search…', icon: Icon, className = '' }) {
  return (
    <div className={`relative ${className}`}>
      {Icon && <Icon size={16} className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" aria-hidden="true" />}
      <input
        type="search"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        aria-label={placeholder}
        className={`${CONTROL} h-9 ${Icon ? 'pl-9' : ''}`}
      />
    </div>
  )
}
