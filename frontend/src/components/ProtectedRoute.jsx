import { Navigate, useLocation } from 'react-router-dom'
import { clearSession, getToken, getUser, homePathFor, isExpired } from '../lib/session'

// Client-side routing guard only; the backend enforces roles on every request.
function ProtectedRoute({ children, allowedRoles }) {
  const location = useLocation()
  const user = getUser()

  if (getToken() && isExpired()) {
    clearSession()
    return <Navigate to="/login?expired=1" replace state={{ from: location.pathname }} />
  }
  if (!getToken() || !user) {
    return <Navigate to="/login" replace state={{ from: location.pathname }} />
  }
  if (allowedRoles && !allowedRoles.includes(user.role)) {
    // Signed in, but this page belongs to another role: go to their own home.
    return <Navigate to={homePathFor(user.role)} replace />
  }
  return children
}

export default ProtectedRoute
