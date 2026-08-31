import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter, Routes, Route } from 'react-router-dom'
import './index.css'
import App from './App.jsx'
import LandingPage from './components/LandingPage.jsx'
import StudentsPage from './components/StudentsPage.jsx'
import VisitorsPage from './components/VisitorsPage.jsx'
import StaffPage from './components/StaffPage.jsx'
import ClassesPage from './components/ClassesPage.jsx'
import LoginPage from './components/LoginPage.jsx'
import ProtectedRoute from './components/ProtectedRoute.jsx'
import MyProfilePage from './components/MyProfilePage.jsx'
import MyClassPage from './components/MyClassPage.jsx'

createRoot(document.getElementById('root')).render(
  <StrictMode>
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<LandingPage />} />
        <Route path="/login" element={<LoginPage />} />
        <Route path="/dashboard" element={<ProtectedRoute allowedRoles={['admin']}><App /></ProtectedRoute>} />
        <Route path="/students" element={<ProtectedRoute allowedRoles={['admin']}><StudentsPage /></ProtectedRoute>} />
        <Route path="/visitors" element={<ProtectedRoute allowedRoles={['admin']}><VisitorsPage /></ProtectedRoute>} />
        <Route path="/staff" element={<ProtectedRoute allowedRoles={['admin']}><StaffPage /></ProtectedRoute>} />
        <Route path="/classes" element={<ProtectedRoute allowedRoles={['admin']}><ClassesPage /></ProtectedRoute>} />
        <Route path="/my-profile" element={<ProtectedRoute allowedRoles={['student']}><MyProfilePage /></ProtectedRoute>} />
        <Route path="/my-class" element={<ProtectedRoute allowedRoles={['teacher']}><MyClassPage /></ProtectedRoute>} />
      </Routes>
    </BrowserRouter>
  </StrictMode>,
)
