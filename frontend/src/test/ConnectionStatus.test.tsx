import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'
import {
  installApiMock,
  jsonResponse,
  makeListResponse,
} from './savedCasesFixtures'
import { renderApp } from './testUtils'

describe('ConnectionStatus health indicator', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
    vi.restoreAllMocks()
  })

  it('renders Connected when health succeeds', async () => {
    installApiMock((input) => {
      const url = String(input)
      if (url.includes('/cases/saved')) {
        return jsonResponse(makeListResponse([]))
      }
      throw new Error(`Unexpected fetch: ${url}`)
    })

    renderApp({ initialEntries: ['/dashboard'] })

    expect(await screen.findByText('API: Connected')).toBeInTheDocument()
  })

  it('renders Unavailable with a retry control when health fails', async () => {
    let healthCalls = 0
    const fetchMock = installApiMock(
      (input) => {
        const url = String(input)
        if (url.includes('/health')) {
          healthCalls += 1
          if (healthCalls === 1) {
            throw new TypeError('Failed to fetch')
          }
          return jsonResponse({ status: 'healthy', service: 'GrievanceHub' })
        }
        if (url.includes('/cases/saved')) {
          return jsonResponse(makeListResponse([]))
        }
        throw new Error(`Unexpected fetch: ${url}`)
      },
      { autoHealth: false },
    )

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
