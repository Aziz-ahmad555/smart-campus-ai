import { Navigate } from 'react-router-dom'

function ProtectedRoute({ children, allowedRoles }) {
  const token = localStorage.getItem('sentra_token')
  const userJson = localStorage.getItem('sentra_user')
  const user = userJson ? JSON.parse(userJson) : null

  if (!token || !user) {
    return <Navigate to="/login" replace />
  }

  if (allowedRoles && !allowedRoles.includes(user.role)) {
    // Logged in, but wrong role for this page — send them to their own home
    if (user.role === 'teacher') return <Navigate to="/my-class" replace />
    if (user.role === 'student') return <Navigate to="/my-profile" replace />
    return <Navigate to="/dashboard" replace />
  }

  return children
}

export default ProtectedRoute
