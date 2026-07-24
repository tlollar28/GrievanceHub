import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { renderApp } from './testUtils'

function jsonResponse(payload: unknown, status = 200): Response {
  return {
    ok: status >= 200 && status < 300,
    status,
    headers: new Headers({ 'content-type': 'application/json' }),
    json: async () => payload,
  } as Response
}

describe('ConnectionStatus health indicator', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
    vi.restoreAllMocks()
  })

  it('renders Connected when health succeeds', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(
        jsonResponse({ status: 'healthy', service: 'GrievanceHub' }),
      ),
    )

    renderApp({ initialEntries: ['/dashboard'] })

    expect(await screen.findByText('API: Connected')).toBeInTheDocument()
  })

  it('renders Unavailable with a retry control when health fails', async () => {
    const fetchMock = vi
      .fn()
      .mockRejectedValueOnce(new TypeError('Failed to fetch'))
      .mockResolvedValueOnce(
        jsonResponse({ status: 'healthy', service: 'GrievanceHub' }),
      )

    vi.stubGlobal('fetch', fetchMock)

    const user = userEvent.setup()
    renderApp({ initialEntries: ['/dashboard'] })

    expect(await screen.findByText('API: Unavailable')).toBeInTheDocument()
    const retry = screen.getByRole('button', { name: 'Retry' })
    expect(retry).toBeInTheDocument()

    await user.click(retry)

    await waitFor(() => {
      expect(screen.getByText('API: Connected')).toBeInTheDocument()
    })
    expect(fetchMock.mock.calls.length).toBeGreaterThanOrEqual(2)
  })
})
