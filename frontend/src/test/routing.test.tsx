import { screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { renderApp } from './testUtils'

describe('routing foundations', () => {
  beforeEach(() => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: true,
        status: 200,
        headers: new Headers({ 'content-type': 'application/json' }),
        json: async () => ({ status: 'healthy', service: 'GrievanceHub' }),
      }),
    )
  })

  afterEach(() => {
    vi.unstubAllGlobals()
    vi.restoreAllMocks()
  })

  it('redirects root to /dashboard', async () => {
    const { router } = renderApp({ initialEntries: ['/'] })

    await waitFor(() => {
      expect(router.state.location.pathname).toBe('/dashboard')
    })
    expect(
      await screen.findByRole('heading', { name: 'Dashboard' }),
    ).toBeInTheDocument()
  })

  it('renders a usable not-found page for unknown routes', async () => {
    renderApp({ initialEntries: ['/this-route-does-not-exist'] })

    expect(
      await screen.findByRole('heading', { name: 'Page not found' }),
    ).toBeInTheDocument()
    expect(
      screen.getByRole('link', { name: 'Return to Dashboard' }),
    ).toBeInTheDocument()
  })
})
