import { History } from 'lucide-react'
import { Button } from './Button'

// "Load older events" at the end of a paginated, newest-first list.
export function LoadOlder({ hasOlder, loading, onClick }) {
  if (!hasOlder) return null
  return (
    <div className="flex justify-center border-t border-slate-100 py-3 dark:border-slate-800">
      <Button variant="ghost" size="sm" icon={History} loading={loading} onClick={onClick}>
        Load older events
      </Button>
    </div>
  )
}
