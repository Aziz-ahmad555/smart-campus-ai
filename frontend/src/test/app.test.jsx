import { describe, expect, it, vi } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter, Route, Routes, useLocation } from 'react-router-dom'
import LoginPage from '../pages/LoginPage.jsx'
import StudentsPage from '../pages/StudentsPage.jsx'
import ProtectedRoute from '../components/ProtectedRoute.jsx'
import { ToastProvider } from '../components/ui/Toast.jsx'
import { api } from '../lib/api'
import { saveSession } from '../lib/session'

const inAnHour = () => Math.floor(Date.now() / 1000) + 3600

function signIn(role) {
  saveSession({ token: 'test-token', user: { username: role, role, full_name: `Test ${role}` }, expires_at: inAnHour() })
}

function Where() {
  const location = useLocation()
  return <p data-testid="where">{location.pathname + location.search}</p>
}

function renderAt(path, element, routePath = path.split('?')[0]) {
  return render(
    <ToastProvider>
      <MemoryRouter initialEntries={[path]}>
        <Routes>
          <Route path={routePath} element={element} />
          <Route path="*" element={<Where />} />
        </Routes>
      </MemoryRouter>
    </ToastProvider>,
  )
}

describe('LoginPage', () => {
  it('renders the sign-in form with labelled fields', () => {
    renderAt('/login', <LoginPage />)
    expect(screen.getByRole('heading', { name: 'Sign in' })).toBeInTheDocument()
    expect(screen.getByLabelText(/Username/)).toBeRequired()
    expect(screen.getByLabelText(/^Password/)).toHaveAttribute('type', 'password')
    expect(screen.getByRole('button', { name: 'Sign in with fingerprint' })).toBeInTheDocument()
    expect(screen.queryByText(/session has expired/)).not.toBeInTheDocument()
  })

  it('explains an expired session', () => {
    renderAt('/login?expired=1', <LoginPage />)
    expect(screen.getByText('Your session has expired. Please sign in again.')).toBeInTheDocument()
  })
})

describe('ProtectedRoute', () => {
  const guarded = (
    <ProtectedRoute allowedRoles={['admin']}>
      <p>secret admin page</p>
    </ProtectedRoute>
  )

  it('sends signed-out visitors to the login page', () => {
    renderAt('/students', guarded)
    expect(screen.queryByText('secret admin page')).not.toBeInTheDocument()
    expect(screen.getByTestId('where')).toHaveTextContent('/login')
  })

  it('sends other roles to their own home page', () => {
    signIn('teacher')
    renderAt('/students', guarded)
    expect(screen.getByTestId('where')).toHaveTextContent('/my-class')
  })

  it('treats an expired session as signed out', () => {
    saveSession({ token: 't', user: { username: 'a', role: 'admin' }, expires_at: 1 })
    renderAt('/students', guarded)
    expect(screen.getByTestId('where')).toHaveTextContent('/login?expired=1')
    expect(localStorage.getItem('sentra_token')).toBeNull()
  })

  it('shows the page to the right role', () => {
    signIn('admin')
    renderAt('/students', guarded)
    expect(screen.getByText('secret admin page')).toBeInTheDocument()
  })
})

describe('StudentsPage', () => {
  it('shows an error with a retry button when the backend is unreachable', async () => {
    signIn('admin')
    vi.spyOn(globalThis, 'fetch').mockRejectedValue(new TypeError('Failed to fetch'))
    renderAt('/students', <StudentsPage />)

    expect(await screen.findByText(/Cannot reach the server/)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Retry' })).toBeInTheDocument()
    // A failed load must not claim the list is empty.
    expect(screen.queryByText('No students yet')).not.toBeInTheDocument()
  })

  it('lists students returned by the API, sending the session in the header', async () => {
    signIn('admin')
    const fetchMock = vi.spyOn(globalThis, 'fetch').mockImplementation(async (url) => {
      const body = String(url).includes('/students')
        ? { students: [{ id: 1, name: 'Demo Student Alpha', roll_number: 'DEMO-001', photo_folder: 'DemoStudentAlpha', class_name: 'Grade 9 - A', created_at: '2026-09-01T10:00:00' }] }
        : { classes: [] }
      return new Response(JSON.stringify(body), { status: 200 })
    })
    renderAt('/students', <StudentsPage />)

    expect(await screen.findByText('Demo Student Alpha')).toBeInTheDocument()
    const [url, options] = fetchMock.mock.calls.find(([u]) => String(u).includes('/students'))
    expect(String(url)).not.toContain('token=')
    expect(options.headers.Authorization).toBe('Bearer test-token')
  })
})

describe('api()', () => {
  it('ends the session and goes to login when the backend answers 401', async () => {
    signIn('admin')
    const assign = vi.fn()
    vi.spyOn(window, 'location', 'get').mockReturnValue({ ...window.location, pathname: '/students', assign })
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(new Response(JSON.stringify({ detail: 'Not signed in or session expired' }), { status: 401 }))

    await expect(api('/students', { auth: true })).rejects.toThrow('Not signed in or session expired')
    expect(localStorage.getItem('sentra_token')).toBeNull()
    await waitFor(() => expect(assign).toHaveBeenCalledWith('/login?expired=1'))
  })
})
