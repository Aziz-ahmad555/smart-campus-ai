import { Link } from 'react-router-dom'
import { Compass } from 'lucide-react'
import { getToken, getUser, homePathFor } from '../lib/session'

export default function NotFoundPage() {
  const user = getUser()
  const home = getToken() && user ? homePathFor(user.role) : '/'
  return (
    <div className="flex min-h-screen flex-col items-center justify-center px-6 text-center">
      <div className="mb-5 flex h-12 w-12 items-center justify-center rounded-full bg-slate-100 text-slate-500 dark:bg-slate-800 dark:text-slate-400">
        <Compass size={22} aria-hidden="true" />
      </div>
      <p className="text-sm font-medium text-blue-600 dark:text-blue-400">404</p>
      <h1 className="mt-1 text-2xl font-semibold tracking-tight text-slate-900 dark:text-white">Page not found</h1>
      <p className="mt-2 text-sm text-slate-500 dark:text-slate-400">The page you&apos;re looking for doesn&apos;t exist or has moved.</p>
      <Link to={home} className="mt-6 inline-flex h-9 items-center rounded-lg bg-blue-600 px-4 text-sm font-medium text-white hover:bg-blue-700">
        Go back home
      </Link>
    </div>
  )
}
