import { screen, waitFor, within } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import {
  installApiMock,
  jsonResponse,
  makeListResponse,
} from './savedCasesFixtures'
import { renderApp } from './testUtils'

describe('AppShell navigation', () => {
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

  it('renders the primary navigation entries', async () => {
    renderApp({ initialEntries: ['/dashboard'] })

    const nav = await screen.findByRole('navigation', {
      name: 'Primary navigation',
    })
    expect(nav).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Dashboard' })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Cases' })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'New Case' })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Help' })).toBeInTheDocument()
    expect(screen.queryByRole('link', { name: 'Sources' })).not.toBeInTheDocument()
  })

  it('marks the active route with aria-current="page"', async () => {
    renderApp({ initialEntries: ['/help'] })

    await screen.findByRole('heading', { name: 'Help' })

    const nav = screen.getByRole('navigation', { name: 'Primary navigation' })
    const helpLink = within(nav).getByRole('link', { name: 'Help' })
    await waitFor(() => {
      expect(helpLink).toHaveAttribute('aria-current', 'page')
    })

    expect(
      within(nav).getByRole('link', { name: 'Dashboard' }),
    ).not.toHaveAttribute('aria-current')
  })
})
