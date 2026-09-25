// Consistent table styling; pages supply rows.
export function Table({ columns, children, className = '' }) {
  return (
    <div className={`overflow-x-auto ${className}`}>
      <table className="w-full text-left text-sm">
        <thead className="sticky top-0 z-10 bg-slate-50/95 backdrop-blur dark:bg-slate-900/95">
          <tr className="text-xs font-medium text-slate-500 dark:text-slate-400">
            {columns.map((c) => (
              <th key={c.key || c.label} scope="col" className={`whitespace-nowrap px-5 py-3 font-medium ${c.className || ''}`}>
                {c.label}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>{children}</tbody>
      </table>
    </div>
  )
}

export function Row({ children, className = '' }) {
  return (
    <tr className={`border-t border-slate-100 transition-colors hover:bg-slate-50/70 dark:border-slate-800 dark:hover:bg-slate-800/40 ${className}`}>
      {children}
    </tr>
  )
}

export function Cell({ children, className = '' }) {
  return <td className={`px-5 py-3.5 align-middle ${className}`}>{children}</td>
}

export function EmptyRow({ colSpan, children }) {
  return (
    <tr>
      <td colSpan={colSpan}>{children}</td>
    </tr>
  )
}
