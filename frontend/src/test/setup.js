import '@testing-library/jest-dom/vitest'
import { afterEach, vi } from 'vitest'
import { cleanup } from '@testing-library/react'

// jsdom has no matchMedia; the theme code asks it for the OS preference.
window.matchMedia ||= vi.fn(() => ({ matches: false, addEventListener() {}, removeEventListener() {} }))

afterEach(() => {
  cleanup()
  localStorage.clear()
})
