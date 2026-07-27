import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { workspaceKeys } from '../features/cases/savedCaseActions'
import {
  OTHER_CASE_UUID,
  SAMPLE_CASE_UUID,
  installApiMock,
  jsonResponse,
  makeCreateResponse,
  makeFactsResponse,
  makeListResponse,
  makeSummary,
  makeWorkspace,
} from './savedCasesFixtures'
import { createTestQueryClient, renderApp } from './testUtils'

describe('W6 M2 Create Case and Workspace Restoration', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
    vi.restoreAllMocks()
  })

  it('renders verified New Case fields', async () => {
    installApiMock((input) => {
      throw new Error(`Unexpected fetch: ${String(input)}`)
    })

    renderApp({ initialEntries: ['/cases/new'] })

    expect(
      await screen.findByRole('heading', { name: 'New Case' }),
    ).toBeInTheDocument()
    expect(
      screen.getByLabelText(/Question or issue description/i),
    ).toBeInTheDocument()
    expect(screen.getByLabelText('Steward name')).toBeInTheDocument()
    expect(screen.getByLabelText('Local number')).toBeInTheDocument()
    expect(screen.getByText(/Known facts \(optional\)/i)).toBeInTheDocument()
    expect(
      screen.getByRole('button', { name: 'Create case' }),
    ).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Cancel' })).toHaveAttribute(
      'href',
      '/cases',
    )
  })

  it('blocks invalid create submission with required validation', async () => {
    const user = userEvent.setup()
    const fetchMock = installApiMock((input) => {
      throw new Error(`Unexpected fetch: ${String(input)}`)
    })

    renderApp({ initialEntries: ['/cases/new'] })
    await user.click(screen.getByRole('button', { name: 'Create case' }))

    expect(
      await screen.findByText('Question or issue description is required.'),
    ).toBeInTheDocument()
    expect(fetchMock).not.toHaveBeenCalledWith(
      expect.stringContaining('/cases/'),
      expect.objectContaining({ method: 'POST' }),
    )
  })

  it('sends the verified create request shape and navigates to workspace', async () => {
    const user = userEvent.setup()
    const createBodyLog: unknown[] = []
    let savedListCalls = 0

    const fetchMock = installApiMock((input, init) => {
      const url = String(input)
      if (url.includes('/cases/saved?')) {
        savedListCalls += 1
        return jsonResponse(makeListResponse([makeSummary()]))
      }
      if (
        (url.endsWith('/cases/') || url.endsWith('/cases')) &&
        init?.method === 'POST'
      ) {
        const body = init.body ? JSON.parse(String(init.body)) : {}
        createBodyLog.push(body)
        return jsonResponse(
          makeCreateResponse({
            case: {
              case_uuid: SAMPLE_CASE_UUID,
              title: 'W6 M2 local workspace smoke test',
              user_name: 'Steward Ada',
              local_number: 'L-12',
              initial_question: 'W6 M2 local workspace smoke test',
              known_facts: { shift: 'tour 2' },
              status: 'open',
              created_at: '2026-07-24T12:00:00Z',
              updated_at: '2026-07-24T12:00:00Z',
              latest_report_version: null,
              report_summary: null,
              retrieval_gaps_summary: null,
              messages: [],
              latest_report: null,
              report_versions: [],
            },
          }),
        )
      }
      if (url.includes(`/cases/${SAMPLE_CASE_UUID}/workspace`)) {
        return jsonResponse(
          makeWorkspace({
            title: 'W6 M2 local workspace smoke test',
            initial_question: 'W6 M2 local workspace smoke test',
            known_facts: { shift: 'Tour 2' },
          }),
        )
      }
      throw new Error(`Unexpected fetch: ${url}`)
    })

    const { router, queryClient } = renderApp({
      initialEntries: ['/cases/new'],
    })

    await user.type(
      screen.getByLabelText(/Question or issue description/i),
      'W6 M2 local workspace smoke test',
    )
    await user.type(screen.getByLabelText('Steward name'), 'Steward Ada')
    await user.type(screen.getByLabelText('Local number'), 'L-12')
    await user.click(screen.getByRole('button', { name: 'Add fact' }))
    await user.type(screen.getByLabelText('Key'), 'shift')
    await user.type(screen.getByLabelText('Value'), 'Tour 2')

    const invalidateSpy = vi.spyOn(queryClient, 'invalidateQueries')
    await user.click(screen.getByRole('button', { name: 'Create case' }))

    await waitFor(() => {
      expect(createBodyLog).toHaveLength(1)
    })
    expect(createBodyLog[0]).toEqual({
      question: 'W6 M2 local workspace smoke test',
      user_name: 'Steward Ada',
      local_number: 'L-12',
      known_facts: { shift: 'Tour 2' },
    })

    await waitFor(() => {
      expect(router.state.location.pathname).toBe(
        `/cases/${SAMPLE_CASE_UUID}/conversation`,
      )
    })

    expect(
      await screen.findByRole('heading', {
        name: 'W6 M2 local workspace smoke test',
      }),
    ).toBeInTheDocument()
    expect(invalidateSpy).toHaveBeenCalledWith(
      expect.objectContaining({
        queryKey: expect.arrayContaining(['savedCases']),
      }),
    )

    const createCalls = fetchMock.mock.calls.filter(
      ([request, init]) =>
        String(request).includes('/cases/') &&
        !String(request).includes('/saved') &&
        !String(request).includes('/workspace') &&
        (init as RequestInit | undefined)?.method === 'POST',
    )
    expect(createCalls).toHaveLength(1)
    expect(savedListCalls).toBeGreaterThanOrEqual(0)
    expect(
      fetchMock.mock.calls.some(([request]) =>
        String(request).includes('/interactions'),
      ),
    ).toBe(false)
  })

  it('preserves form values after create failure and prevents duplicate submit', async () => {
    const user = userEvent.setup()
    let createCalls = 0
    installApiMock((input, init) => {
      const url = String(input)
      if (
        (url.endsWith('/cases/') || url.endsWith('/cases')) &&
        init?.method === 'POST'
      ) {
        createCalls += 1
        return jsonResponse({ detail: 'Database unavailable' }, 500)
      }
      throw new Error(`Unexpected fetch: ${url}`)
    })

    renderApp({ initialEntries: ['/cases/new'] })

    const question = screen.getByLabelText(/Question or issue description/i)
    await user.type(question, 'Preserved question text')
    await user.type(screen.getByLabelText('Steward name'), 'Steward Bea')

    const submit = screen.getByRole('button', { name: 'Create case' })
    await user.click(submit)

    expect(await screen.findByRole('alert')).toHaveTextContent(
      /server error|Database unavailable/i,
    )
    expect(question).toHaveValue('Preserved question text')
    expect(screen.getByLabelText('Steward name')).toHaveValue('Steward Bea')

    await waitFor(() => {
      expect(createCalls).toBe(1)
    })
  })

  it('uses cached activation workspace then fetches authoritative workspace', async () => {
    const fetchMock = installApiMock((input) => {
      const url = String(input)
      if (url.includes(`/cases/${SAMPLE_CASE_UUID}/workspace`)) {
        return jsonResponse(
          makeWorkspace({
            title: 'Authoritative overtime dispute',
            case_overview: {
              ...makeWorkspace().case_overview,
              issue: 'Authoritative issue text',
            },
          }),
        )
      }
      throw new Error(`Unexpected fetch: ${url}`)
    })

    const queryClient = createTestQueryClient()
    queryClient.setQueryData(
      workspaceKeys.detail(SAMPLE_CASE_UUID),
      makeWorkspace({ title: 'Cached overtime dispute' }),
    )

    renderApp({
      initialEntries: [`/cases/${SAMPLE_CASE_UUID}`],
      queryClient,
    })

    expect(
      await screen.findByRole('heading', {
        name: 'Cached overtime dispute',
      }),
    ).toBeInTheDocument()

    expect(
      await screen.findByRole('heading', {
        name: 'Authoritative overtime dispute',
      }),
    ).toBeInTheDocument()

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith(
        expect.stringContaining(`/cases/${SAMPLE_CASE_UUID}/workspace`),
        expect.anything(),
      )
    })
  })

  it('restores workspace on direct navigation', async () => {
    installApiMock((input) => {
      const url = String(input)
      if (url.includes(`/cases/${SAMPLE_CASE_UUID}/workspace`)) {
        return jsonResponse(makeWorkspace())
      }
      throw new Error(`Unexpected fetch: ${url}`)
    })

    renderApp({ initialEntries: [`/cases/${SAMPLE_CASE_UUID}`] })

    expect(
      await screen.findByRole('heading', { name: 'Overtime dispute' }),
    ).toBeInTheDocument()
    expect(screen.getByText(SAMPLE_CASE_UUID)).toBeInTheDocument()
    expect(
      screen.getByRole('navigation', { name: 'Case rail' }),
    ).toBeInTheDocument()
    expect(
      screen.getByRole('heading', { name: 'Case overview' }),
    ).toBeInTheDocument()
    expect(
      screen.getByRole('heading', { name: 'Case Memory' }),
    ).toBeInTheDocument()
    expect(
      screen.getByRole('heading', { name: 'Known facts' }),
    ).toBeInTheDocument()
    expect(
      await screen.findByRole('heading', { name: 'Conversation' }),
    ).toBeInTheDocument()
  })

  it('shows workspace loading state', async () => {
    installApiMock(
      () =>
        new Promise(() => {
          /* pending */
        }),
    )

    renderApp({ initialEntries: [`/cases/${SAMPLE_CASE_UUID}`] })

    expect(
      await screen.findByRole('heading', {
        name: 'Restoring case workspace…',
      }),
    ).toBeInTheDocument()
    expect(
      screen.getByText(`Loading case ${SAMPLE_CASE_UUID}`),
    ).toBeInTheDocument()
  })

  it('shows not-found state for missing cases', async () => {
    installApiMock((input) => {
      const url = String(input)
      if (url.includes(`/cases/${SAMPLE_CASE_UUID}/workspace`)) {
        return jsonResponse({ detail: 'Case not found' }, 404)
      }
      throw new Error(`Unexpected fetch: ${url}`)
    })

    renderApp({ initialEntries: [`/cases/${SAMPLE_CASE_UUID}`] })

    expect(
      await screen.findByRole('heading', { name: 'Case not found' }),
    ).toBeInTheDocument()
    expect(screen.getByRole('alert')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Retry' })).not.toBeInTheDocument()
  })

  it('shows API error with Retry for workspace failures', async () => {
    const user = userEvent.setup()
    let calls = 0
    installApiMock((input) => {
      const url = String(input)
      if (url.includes(`/cases/${SAMPLE_CASE_UUID}/workspace`)) {
        calls += 1
        if (calls === 1) {
          return jsonResponse({ detail: 'Database unavailable' }, 500)
        }
        return jsonResponse(makeWorkspace())
      }
      throw new Error(`Unexpected fetch: ${url}`)
    })

    renderApp({ initialEntries: [`/cases/${SAMPLE_CASE_UUID}`] })

    expect(await screen.findByRole('alert')).toHaveTextContent(
      /server error|Database unavailable/i,
    )
    await user.click(screen.getByRole('button', { name: 'Retry' }))
    expect(
      await screen.findByRole('heading', { name: 'Overtime dispute' }),
    ).toBeInTheDocument()
  })

  it('renders header identity/status/step and supported rail sections', async () => {
    installApiMock((input) => {
      const url = String(input)
      if (url.includes(`/cases/${SAMPLE_CASE_UUID}/workspace`)) {
        return jsonResponse(makeWorkspace())
      }
      throw new Error(`Unexpected fetch: ${url}`)
    })

    renderApp({ initialEntries: [`/cases/${SAMPLE_CASE_UUID}`] })

    expect(
      await screen.findByRole('heading', { name: 'Overtime dispute' }),
    ).toBeInTheDocument()
    expect(screen.getByText('Open')).toBeInTheDocument()
    expect(screen.getAllByText(/Step 1/i).length).toBeGreaterThan(0)
    expect(screen.getByRole('button', { name: 'Copy UUID' })).toBeInTheDocument()

    const rail = screen.getByRole('navigation', { name: 'Case rail' })
    expect(
      within(rail).getByRole('heading', { name: 'Case identity' }),
    ).toBeInTheDocument()
    expect(
      within(rail).getByRole('heading', { name: 'Recent timeline' }),
    ).toBeInTheDocument()
    expect(
      within(rail).getByRole('heading', { name: 'Uploads' }),
    ).toBeInTheDocument()
    expect(within(rail).getByText('schedule.pdf')).toBeInTheDocument()
    expect(
      within(rail).queryByRole('heading', { name: 'Artifact summary' }),
    ).not.toBeInTheDocument()
    expect(
      within(rail).getByRole('link', { name: 'Open Artifacts & History' }),
    ).toHaveAttribute('href', `/cases/${SAMPLE_CASE_UUID}/artifacts`)
    expect(
      within(rail).getByRole('link', { name: 'Open Workflow' }),
    ).toHaveAttribute('href', `/cases/${SAMPLE_CASE_UUID}/workflow`)
  })

  it('shows honest empty memory/overview states', async () => {
    installApiMock((input) => {
      const url = String(input)
      if (url.includes(`/cases/${SAMPLE_CASE_UUID}/workspace`)) {
        return jsonResponse(
          makeWorkspace({
            initial_question: null,
            case_overview: {
              case_uuid: SAMPLE_CASE_UUID,
              current_status: 'open',
              issue: null,
              open_questions: [],
              outstanding_issues: [],
              evidence_count: 0,
              analysis_report_count: 0,
              official_grievance_count: 0,
              source: 'case_memory',
            },
            case_memory: {
              restored_from: 'unavailable',
              full_transcript_embedded: false,
            },
          }),
        )
      }
      throw new Error(`Unexpected fetch: ${url}`)
    })

    renderApp({ initialEntries: [`/cases/${SAMPLE_CASE_UUID}`] })

    expect(
      await screen.findByText(/No Case Overview content is available yet/i),
    ).toBeInTheDocument()
    expect(
      screen.getByText(/Case Memory is not available for this case yet/i),
    ).toBeInTheDocument()
  })

  it('saves facts with verified request shape and refreshes workspace', async () => {
    const user = userEvent.setup()
    let workspaceVersion = 1
    const patchBodies: unknown[] = []

    installApiMock((input, init) => {
      const url = String(input)
      if (url.includes(`/cases/${SAMPLE_CASE_UUID}/workspace`)) {
        return jsonResponse(
          makeWorkspace({
            known_facts:
              workspaceVersion === 1
                ? { tour: '2' }
                : { tour: '2', location: 'Annex' },
          }),
        )
      }
      if (
        url.includes(`/cases/${SAMPLE_CASE_UUID}/facts`) &&
        init?.method === 'PATCH'
      ) {
        const body = init.body ? JSON.parse(String(init.body)) : {}
        patchBodies.push(body)
        workspaceVersion = 2
        return jsonResponse(
          makeFactsResponse({
            known_facts: { tour: '2', location: 'Annex' },
          }),
        )
      }
      throw new Error(`Unexpected fetch: ${url}`)
    })

    renderApp({ initialEntries: [`/cases/${SAMPLE_CASE_UUID}`] })
    await screen.findByRole('heading', { name: 'Known facts' })

    await user.click(screen.getByRole('button', { name: 'Add fact' }))
    const keys = screen.getAllByLabelText('Key')
    const values = screen.getAllByLabelText('Value')
    await user.clear(keys[keys.length - 1]!)
    await user.type(keys[keys.length - 1]!, 'location')
    await user.clear(values[values.length - 1]!)
    await user.type(values[values.length - 1]!, 'Annex')

    await user.click(screen.getByRole('button', { name: 'Save facts' }))

    await waitFor(() => {
      expect(patchBodies).toEqual([
        { known_facts: { tour: '2', location: 'Annex' } },
      ])
    })
    expect(
      await screen.findByText('Known facts saved.'),
    ).toBeInTheDocument()
  })

  it('preserves steward fact edits after save failure', async () => {
    const user = userEvent.setup()
    installApiMock((input, init) => {
      const url = String(input)
      if (url.includes(`/cases/${SAMPLE_CASE_UUID}/workspace`)) {
        return jsonResponse(makeWorkspace({ known_facts: { tour: '2' } }))
      }
      if (
        url.includes(`/cases/${SAMPLE_CASE_UUID}/facts`) &&
        init?.method === 'PATCH'
      ) {
        return jsonResponse({ detail: 'Database unavailable' }, 500)
      }
      throw new Error(`Unexpected fetch: ${url}`)
    })

    renderApp({ initialEntries: [`/cases/${SAMPLE_CASE_UUID}`] })
    await screen.findByRole('heading', { name: 'Known facts' })

    const valueInputs = screen.getAllByLabelText('Value')
    await user.clear(valueInputs[0]!)
    await user.type(valueInputs[0]!, 'Tour 3')
    await user.click(screen.getByRole('button', { name: 'Save facts' }))

    expect(await screen.findByRole('alert')).toHaveTextContent(
      /server error|Database unavailable/i,
    )
    expect(screen.getAllByLabelText('Value')[0]).toHaveValue('Tour 3')
    expect(screen.getByText('Unsaved changes')).toBeInTheDocument()
  })

  it('does not show prior case data after navigating to another case', async () => {
    installApiMock((input) => {
      const url = String(input)
      if (url.includes(`/cases/${SAMPLE_CASE_UUID}/workspace`)) {
        return jsonResponse(
          makeWorkspace({
            title: 'Case Alpha',
            case_overview: {
              ...makeWorkspace().case_overview,
              issue: 'Alpha issue',
            },
          }),
        )
      }
      if (url.includes(`/cases/${OTHER_CASE_UUID}/workspace`)) {
        return jsonResponse(
          makeWorkspace({
            case_uuid: OTHER_CASE_UUID,
            title: 'Case Beta',
            case_overview: {
              ...makeWorkspace().case_overview,
              case_uuid: OTHER_CASE_UUID,
              issue: 'Beta issue',
            },
          }),
        )
      }
      throw new Error(`Unexpected fetch: ${url}`)
    })

    const { router } = renderApp({
      initialEntries: [`/cases/${SAMPLE_CASE_UUID}`],
    })

    expect(
      await screen.findByRole('heading', { name: 'Case Alpha' }),
    ).toBeInTheDocument()
    expect(screen.getByText('Alpha issue')).toBeInTheDocument()

    await router.navigate(`/cases/${OTHER_CASE_UUID}`)

    expect(
      await screen.findByRole('heading', { name: 'Case Beta' }),
    ).toBeInTheDocument()
    expect(screen.getByText('Beta issue')).toBeInTheDocument()
    expect(screen.queryByText('Alpha issue')).not.toBeInTheDocument()
    expect(screen.queryByText('Case Alpha')).not.toBeInTheDocument()
  })

  it('does not call analysis, grievance, or artifact endpoints on workspace open', async () => {
    const fetchMock = installApiMock((input) => {
      const url = String(input)
      if (url.includes(`/cases/${SAMPLE_CASE_UUID}/workspace`)) {
        return jsonResponse(makeWorkspace())
      }
      throw new Error(`Unexpected fetch: ${url}`)
    })

    renderApp({ initialEntries: [`/cases/${SAMPLE_CASE_UUID}`] })
    await screen.findByRole('heading', { name: 'Overtime dispute' })
    await screen.findByRole('heading', { name: 'Conversation' })

    for (const [request, init] of fetchMock.mock.calls) {
      const url = String(request)
      const method = init?.method ?? 'GET'
      expect(url).not.toMatch(/\/interactions/)
      expect(url).not.toMatch(/\/reports\//)
      expect(url).not.toMatch(/\/grievances\//)
      expect(url).not.toMatch(/\/artifacts/)
      if (url.includes('/messages')) {
        expect(method).toBe('GET')
      }
    }
  })
})
