import { Suspense, lazy } from 'react'
import { Routes, Route } from 'react-router-dom'
import ProtectedRoute from './components/ProtectedRoute.jsx'
import LandingPage from './pages/LandingPage.jsx'
import LoginPage from './pages/LoginPage.jsx'
import NotFoundPage from './pages/NotFoundPage.jsx'

// Signed-in pages load on demand, so the landing and login pages stay light.
const DashboardPage = lazy(() => import('./pages/DashboardPage.jsx'))
const StudentsPage = lazy(() => import('./pages/StudentsPage.jsx'))
const StaffPage = lazy(() => import('./pages/StaffPage.jsx'))
const ClassesPage = lazy(() => import('./pages/ClassesPage.jsx'))
const VisitorsPage = lazy(() => import('./pages/VisitorsPage.jsx'))
const MyProfilePage = lazy(() => import('./pages/MyProfilePage.jsx'))
const MyClassPage = lazy(() => import('./pages/MyClassPage.jsx'))

function PageLoader() {
  return (
    <div className="flex min-h-screen items-center justify-center" role="status" aria-label="Loading">
      <div className="h-6 w-6 animate-spin rounded-full border-2 border-slate-300 border-t-blue-600 dark:border-slate-700 dark:border-t-blue-400" />
    </div>
  )
}

const only = (roles, page) => <ProtectedRoute allowedRoles={roles}>{page}</ProtectedRoute>

export default function App() {
  return (
    <Suspense fallback={<PageLoader />}>
      <Routes>
        <Route path="/" element={<LandingPage />} />
        <Route path="/login" element={<LoginPage />} />
        <Route path="/dashboard" element={only(['admin'], <DashboardPage />)} />
        <Route path="/students" element={only(['admin'], <StudentsPage />)} />
        <Route path="/visitors" element={only(['admin'], <VisitorsPage />)} />
        <Route path="/staff" element={only(['admin'], <StaffPage />)} />
        <Route path="/classes" element={only(['admin'], <ClassesPage />)} />
        <Route path="/my-profile" element={only(['student'], <MyProfilePage />)} />
        <Route path="/my-class" element={only(['teacher'], <MyClassPage />)} />
        <Route path="*" element={<NotFoundPage />} />
      </Routes>
    </Suspense>
  )
}
