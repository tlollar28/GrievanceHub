import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { resolveCaseClickAction } from '../features/cases/savedCaseActions'
import {
  CLOSED_CASE_UUID,
  SAMPLE_CASE_UUID,
  installApiMock,
  jsonResponse,
  makeListResponse,
  makeOpenResponse,
  makeReopenResponse,
  makeSummary,
  makeWorkspace,
} from './savedCasesFixtures'
import { renderApp } from './testUtils'

describe('resolveCaseClickAction', () => {
  it('reopens terminal workspace statuses', () => {
    expect(
      resolveCaseClickAction(makeSummary({ workspace_status: 'closed' })),
    ).toBe('reopen_case')
    expect(
      resolveCaseClickAction(makeSummary({ workspace_status: 'settled' })),
    ).toBe('reopen_case')
    expect(
      resolveCaseClickAction(makeSummary({ workspace_status: 'archived' })),
    ).toBe('reopen_case')
  })

  it('opens active workspace statuses', () => {
    expect(
      resolveCaseClickAction(makeSummary({ workspace_status: 'open' })),
    ).toBe('open_case')
    expect(
      resolveCaseClickAction(makeSummary({ workspace_status: 'reopened' })),
    ).toBe('open_case')
    expect(
      resolveCaseClickAction(makeSummary({ workspace_status: 'appealed' })),
    ).toBe('open_case')
  })
})

describe('Saved Cases M1', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
    vi.restoreAllMocks()
  })

  it('loads dashboard cases from GET /cases/saved', async () => {
    const fetchMock = installApiMock((input) => {
      const url = String(input)
      if (url.includes('/cases/saved?')) {
        return jsonResponse(
          makeListResponse([makeSummary()], {
            limit: 10,
            total: 1,
          }),
        )
      }
      throw new Error(`Unexpected fetch: ${url}`)
    })

    renderApp({ initialEntries: ['/dashboard'] })

    expect(
      await screen.findByRole('heading', { name: 'Dashboard' }),
    ).toBeInTheDocument()
    expect(
      await screen.findByRole('button', {
        name: 'Open Overtime dispute',
      }),
    ).toBeInTheDocument()
    expect(screen.getByText('View all cases')).toBeInTheDocument()

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith(
        expect.stringContaining('/cases/saved?'),
        expect.anything(),
      )
    })
  })

  it('applies search and status filters on the Cases page', async () => {
    const user = userEvent.setup()
    const fetchMock = installApiMock((input) => {
      const url = String(input)
      if (url.includes('/cases/saved?')) {
        return jsonResponse(makeListResponse([makeSummary()]))
      }
      throw new Error(`Unexpected fetch: ${url}`)
    })

    const { router } = renderApp({ initialEntries: ['/cases'] })

    await screen.findByRole('heading', { name: 'Cases' })
    await screen.findByRole('button', { name: 'Open Overtime dispute' })

    await user.selectOptions(screen.getByLabelText('Status'), 'closed')

    await waitFor(() => {
      expect(router.state.location.search).toContain('status=closed')
    })

    const search = screen.getByLabelText(/^Search$/)
    await user.clear(search)
    await user.type(search, 'Overtime')
    const filtersSearch = search.closest('form')
    expect(filtersSearch).not.toBeNull()
    await user.click(
      within(filtersSearch as HTMLElement).getByRole('button', {
        name: 'Search',
      }),
    )

    await waitFor(() => {
      expect(router.state.location.search).toContain('search=Overtime')
      expect(router.state.location.search).toContain('status=closed')
    })

    await waitFor(() => {
      const savedCalls = fetchMock.mock.calls.filter(([request]) =>
        String(request).includes('/cases/saved?'),
      )
      expect(savedCalls.length).toBeGreaterThan(1)
      const lastUrl = String(savedCalls[savedCalls.length - 1]?.[0])
      expect(lastUrl).toContain('status=closed')
      expect(lastUrl).toContain('search=Overtime')
    })
  })

  it('opens an active case and navigates to the workspace entry route', async () => {
    const user = userEvent.setup()
    installApiMock((input, init) => {
      const url = String(input)
      if (url.includes('/cases/saved?')) {
        return jsonResponse(makeListResponse([makeSummary()]))
      }
      if (
        url.includes(`/cases/saved/${SAMPLE_CASE_UUID}/open`) &&
        init?.method === 'POST'
      ) {
        return jsonResponse(makeOpenResponse())
      }
      if (url.includes(`/cases/${SAMPLE_CASE_UUID}/workspace`)) {
        return jsonResponse(makeWorkspace())
      }
      throw new Error(`Unexpected fetch: ${url}`)
    })

    const { router } = renderApp({ initialEntries: ['/cases'] })

    await screen.findByRole('button', { name: 'Open Overtime dispute' })
    await user.click(screen.getByRole('button', { name: 'Open' }))

    await waitFor(() => {
      expect(router.state.location.pathname).toBe(
        `/cases/${SAMPLE_CASE_UUID}/conversation`,
      )
    })

    expect(
      await screen.findByRole('heading', { name: 'Overtime dispute' }),
    ).toBeInTheDocument()
    expect(screen.getByText(SAMPLE_CASE_UUID)).toBeInTheDocument()
  })

  it('reopens a closed case via POST .../reopen', async () => {
    const user = userEvent.setup()
    const closed = makeSummary({
      case_uuid: CLOSED_CASE_UUID,
      case_id: 502,
      case_number: '502',
      title: 'Closed overtime case',
      workspace_status: 'closed',
      available_actions: ['open_case', 'reopen_case', 'view_timeline'],
    })

    installApiMock((input, init) => {
      const url = String(input)
      if (url.includes('/cases/saved?')) {
        return jsonResponse(makeListResponse([closed]))
      }
      if (
        url.includes(`/cases/saved/${CLOSED_CASE_UUID}/reopen`) &&
        init?.method === 'POST'
      ) {
        const body = init.body ? JSON.parse(String(init.body)) : {}
        expect(body.source).toBe('manual_ui')
        return jsonResponse(
          makeReopenResponse({
            case: {
              ...closed,
              workspace_status: 'reopened',
            },
          }),
        )
      }
      if (url.includes(`/cases/${CLOSED_CASE_UUID}/workspace`)) {
        return jsonResponse(
          makeWorkspace({
            case_uuid: CLOSED_CASE_UUID,
            title: 'Closed overtime case',
          }),
        )
      }
      throw new Error(`Unexpected fetch: ${url}`)
    })

    const { router } = renderApp({ initialEntries: ['/cases'] })

    await screen.findByRole('button', {
      name: 'Reopen Closed overtime case',
    })
    await user.click(screen.getByRole('button', { name: 'Reopen' }))

    await waitFor(() => {
      expect(router.state.location.pathname).toBe(
        `/cases/${CLOSED_CASE_UUID}/conversation`,
      )
    })
  })

  it('prompts reopen when open returns closed_requires_reopen', async () => {
    const user = userEvent.setup()
    const settled = makeSummary({
      title: 'Settled matter',
      workspace_status: 'settled',
      available_actions: ['open_case', 'reopen_case', 'view_timeline'],
    })

    // Force open path by using open_case resolution only if status weren't terminal —
    // settled is terminal, so row click already reopens. Simulate via open button
    // not being the click path: call Open when somehow available after API says reopen.
    // Use appealed (active) that API unexpectedly returns closed_requires_reopen.
    const odd = makeSummary({
      title: 'Odd status case',
      workspace_status: 'appealed',
      available_actions: ['open_case', 'view_timeline'],
    })

    let reopenCalled = false
    installApiMock((input, init) => {
      const url = String(input)
      if (url.includes('/cases/saved?')) {
        return jsonResponse(makeListResponse([odd]))
      }
      if (
        url.includes(`/cases/saved/${SAMPLE_CASE_UUID}/open`) &&
        init?.method === 'POST'
      ) {
        return jsonResponse(
          makeOpenResponse({
            case: settled,
            action_taken: 'closed_requires_reopen',
            message:
              'Case is settled. Use reopen_case to resume work on the same case workspace.',
            workspace: null,
          }),
        )
      }
      if (
        url.includes(`/cases/saved/${SAMPLE_CASE_UUID}/reopen`) &&
        init?.method === 'POST'
      ) {
        reopenCalled = true
        return jsonResponse(
          makeReopenResponse({
            case: {
              ...settled,
              workspace_status: 'reopened',
            },
          }),
        )
      }
      if (url.includes(`/cases/${SAMPLE_CASE_UUID}/workspace`)) {
        return jsonResponse(makeWorkspace({ title: 'Settled matter' }))
      }
      throw new Error(`Unexpected fetch: ${url}`)
    })

    const { router } = renderApp({ initialEntries: ['/cases'] })

    await user.click(
      await screen.findByRole('button', { name: 'Open Odd status case' }),
    )

    expect(
      await screen.findByRole('region', { name: 'Reopen required' }),
    ).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: 'Reopen case' }))

    await waitFor(() => {
      expect(reopenCalled).toBe(true)
      expect(router.state.location.pathname).toBe(
        `/cases/${SAMPLE_CASE_UUID}/conversation`,
      )
    })
  })

  it('paginates with limit and offset query params', async () => {
    const user = userEvent.setup()
    const page1 = makeSummary({ title: 'Case page one' })
    const page2 = makeSummary({
      case_uuid: CLOSED_CASE_UUID,
      case_id: 502,
      case_number: '502',
      title: 'Case page two',
    })

    installApiMock((input) => {
      const url = String(input)
      if (!url.includes('/cases/saved?')) {
        throw new Error(`Unexpected fetch: ${url}`)
      }
      const parsed = new URL(url, 'http://localhost')
      const offset = Number(parsed.searchParams.get('offset') ?? '0')
      if (offset === 0) {
        return jsonResponse(
          makeListResponse([page1], {
            total: 2,
            limit: 1,
            offset: 0,
            has_more: true,
            count: 1,
          }),
        )
      }
      return jsonResponse(
        makeListResponse([page2], {
          total: 2,
          limit: 1,
          offset: 1,
          has_more: false,
          count: 1,
        }),
      )
    })

    const { router } = renderApp({
      initialEntries: ['/cases?limit=1'],
    })

    expect(
      await screen.findByRole('button', { name: 'Open Case page one' }),
    ).toBeInTheDocument()

    const pagination = screen.getByRole('navigation', { name: 'Pagination' })
    await user.click(within(pagination).getByRole('button', { name: 'Next' }))

    await waitFor(() => {
      expect(router.state.location.search).toContain('offset=1')
    })
    expect(
      await screen.findByRole('button', { name: 'Open Case page two' }),
    ).toBeInTheDocument()
  })

  it('routes global TopBar search to /cases?search=', async () => {
    const user = userEvent.setup()
    installApiMock((input) => {
      const url = String(input)
      if (url.includes('/cases/saved?')) {
        return jsonResponse(makeListResponse([]))
      }
      throw new Error(`Unexpected fetch: ${url}`)
    })

    const { router } = renderApp({ initialEntries: ['/dashboard'] })

    await screen.findByRole('heading', { name: 'Dashboard' })
    const globalSearch = screen.getByRole('search', {
      name: 'Search saved cases',
    })
    await user.type(
      within(globalSearch).getByRole('searchbox', {
        name: 'Search saved cases',
      }),
      '501',
    )
    await user.click(
      within(globalSearch).getByRole('button', { name: 'Search' }),
    )

    await waitFor(() => {
      expect(router.state.location.pathname).toBe('/cases')
      expect(router.state.location.search).toContain('search=501')
    })
  })

  it('shows an accessible error with retry when the list fails', async () => {
    const user = userEvent.setup()
    let calls = 0
    installApiMock((input) => {
      const url = String(input)
      if (url.includes('/cases/saved?')) {
        calls += 1
        if (calls === 1) {
          return jsonResponse({ detail: 'Database unavailable' }, 500)
        }
        return jsonResponse(makeListResponse([makeSummary()]))
      }
      throw new Error(`Unexpected fetch: ${url}`)
    })

    renderApp({ initialEntries: ['/cases'] })

    const alert = await screen.findByRole('alert')
    expect(alert).toHaveTextContent(/server error|Database unavailable/i)

    await user.click(screen.getByRole('button', { name: 'Retry' }))

    expect(
      await screen.findByRole('button', { name: 'Open Overtime dispute' }),
    ).toBeInTheDocument()
  })
})
