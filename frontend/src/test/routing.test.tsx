import { screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import {
  installApiMock,
  jsonResponse,
  makeListResponse,
} from './savedCasesFixtures'
import { renderApp } from './testUtils'

describe('routing foundations', () => {
  beforeEach(() => {
    installApiMock((input) => {
      const url = String(input)
      if (url.includes('/cases/saved')) {
        return jsonResponse(makeListResponse([]))
      }
      throw new Error(`Unexpected fetch: ${url}`)
    })
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
