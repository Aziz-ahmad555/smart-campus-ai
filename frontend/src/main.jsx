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

createRoot(document.getElementById('root')).render(
  <StrictMode>
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<LandingPage />} />
        <Route path="/dashboard" element={<App />} />
        <Route path="/students" element={<StudentsPage />} />
        <Route path="/visitors" element={<VisitorsPage />} />
        <Route path="/staff" element={<StaffPage />} />
        <Route path="/classes" element={<ClassesPage />} />
      </Routes>
    </BrowserRouter>
  </StrictMode>,
)
