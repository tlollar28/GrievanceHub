import { fireEvent, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'
import type {
  ResearchMetaResponse,
  ResearchSearchResponse,
} from '../api/types/research'
import {
  OTHER_CASE_UUID,
  SAMPLE_CASE_UUID,
  installApiMock,
  jsonResponse,
  makeWorkspace,
} from './savedCasesFixtures'
import { renderApp } from './testUtils'

const AUTHORITY_NOTICE =
  'Sources Research searches the indexed authority corpus. Files uploaded under Evidence are case attachments and are not part of authority-corpus retrieval.'

function makeMeta(
  overrides: Partial<ResearchMetaResponse> = {},
): ResearchMetaResponse {
  return {
    source_types: [
      { value: 'CONTRACT', label: 'National Agreement' },
      { value: 'CIM', label: 'Contract Interpretation Manual' },
      { value: 'ELM', label: 'Employee and Labor Relations Manual' },
      { value: 'SUPERVISOR_MANUAL', label: 'Supervisor Manual' },
    ],
    default_limit: 12,
    max_limit: 24,
    default_limit_per_source: 3,
    max_limit_per_source: 5,
    max_offset: 200,
    max_query_chars: 2000,
    authority_notice: AUTHORITY_NOTICE,
    boundary: 'Interim W6 browser-safe read-only research boundary.',
    ...overrides,
  }
}

function makeSearchResponse(
  overrides: Partial<ResearchSearchResponse> = {},
): ResearchSearchResponse {
  return {
    query: 'overtime',
    retrieval_status: 'ok',
    retrieval_status_raw: 'success',
    partial: false,
    result_count: 1,
    total_matched: 1,
    limit: 12,
    offset: 0,
    limit_per_source: 3,
    results: [
      {
        rank: 1,
        source_document_id: 11,
        canonical_source_id: 'contract-na',
        source_title: 'National Agreement Article Text',
        source_type: 'CONTRACT',
        source_type_label: 'National Agreement',
        source_chunk_id: 101,
        chunk_index: 3,
        page_number: 12,
        section: 'Overtime',
        article: '16',
        heading: 'Overtime',
        passage_text: 'Article 16 governs overtime assignments for regulars.',
        excerpt: 'Article 16 governs overtime assignments for regulars.',
        final_relevance_score: 0.81,
        normalized_score: 0.77,
        evidence_role: 'contract_controlling',
        retrieval_agent: 'ContractAgent',
        content_trust: 'indexed_authority',
        provenance: 'CONTRACT · contract_controlling · page 12 · chunk 3',
        metadata: { article: '16', section: 'Overtime', page: 12 },
      },
    ],
    failures: [],
    authority_notice: AUTHORITY_NOTICE,
    ...overrides,
  }
}

function researchHandler(options: {
  searchResponse?: ResearchSearchResponse | (() => ResearchSearchResponse)
  searchStatus?: number
  searchErrorDetail?: string
  delayMs?: number
  metaFailures?: number
} = {}) {
  const workspace = makeWorkspace()
  const otherWorkspace = makeWorkspace({
    case_uuid: OTHER_CASE_UUID,
    title: 'Other case',
  })
  const searchBodies: Array<Record<string, unknown>> = []
  const requestUrls: string[] = []
  const requestHeaders: Array<Record<string, string>> = []
  const sourcesCalls: string[] = []
  const mutationCalls: string[] = []
  let searchCount = 0
  let metaCount = 0

  const fetchMock = installApiMock(
    async (input, init) => {
      const url =
        typeof input === 'string'
          ? input
          : input instanceof URL
            ? input.toString()
            : input.url
      const method = (init?.method ?? 'GET').toUpperCase()
      requestUrls.push(`${method} ${url}`)
      requestHeaders.push((init?.headers as Record<string, string>) ?? {})

      if (
        url.includes('/messages') &&
        (!init?.method || init.method.toUpperCase() === 'GET')
      ) {
        return jsonResponse({
          case_uuid: SAMPLE_CASE_UUID,
          messages: [],
          count: 0,
          limit: 50,
          offset: 0,
          order: 'asc',
          has_more: false,
        })
      }
      if (
        /\/cases\/[^/]+\/artifacts(?:\?|$)/.test(url) &&
        (!init?.method || init.method.toUpperCase() === 'GET')
      ) {
        return jsonResponse({
          case_uuid: SAMPLE_CASE_UUID,
          artifacts: [],
          count: 0,
          limit: 50,
          offset: 0,
          has_more: false,
        })
      }

      if (url.includes('/sources')) {
        sourcesCalls.push(`${method} ${url}`)
        return jsonResponse(
          { detail: 'Protected sources must not be called' },
          500,
        )
      }

      if (
        method !== 'GET' &&
        (url.includes('/interactions') ||
          url.includes('/outcomes') ||
          url.includes('/reports') ||
          url.includes('/grievances') ||
          url.includes('/assets'))
      ) {
        mutationCalls.push(`${method} ${url}`)
      }

      if (url.includes(`/cases/${SAMPLE_CASE_UUID}/workspace`)) {
        return jsonResponse(workspace)
      }
      if (url.includes(`/cases/${OTHER_CASE_UUID}/workspace`)) {
        return jsonResponse(otherWorkspace)
      }
      if (
        url.includes(`/cases/${SAMPLE_CASE_UUID}/workflow`) &&
        method === 'GET'
      ) {
        return jsonResponse({
          case_uuid: SAMPLE_CASE_UUID,
          explicit_state: 'step_1_decision_required',
          current_grievance_step: 'step_1_initial',
          case_status: 'open',
          inferred: false,
          inference_confidence: 'confirmed',
          permitted_next_states: [],
          updated_at: null,
        })
      }
      if (
        url.includes('/cases/') &&
        url.includes('/history') &&
        method === 'GET'
      ) {
        return jsonResponse({
          case_uuid: SAMPLE_CASE_UUID,
          items: [],
          count: 0,
          limit: 50,
          offset: 0,
          has_more: false,
        })
      }
      if (
        url.includes('/cases/') &&
        url.includes('/timeline') &&
        method === 'GET'
      ) {
        return jsonResponse({
          case_uuid: SAMPLE_CASE_UUID,
          events: [],
          count: 0,
          limit: 50,
          offset: 0,
          has_more: false,
        })
      }
      if (url.includes('/research/meta')) {
        metaCount += 1
        if (metaCount <= (options.metaFailures ?? 0)) {
          return jsonResponse(
            {
              detail:
                'psycopg database driver failed at C:\\internal\\database.py',
            },
            503,
          )
        }
        return jsonResponse(makeMeta())
      }
      if (url.includes('/research/sources/') && method === 'GET') {
        return jsonResponse({
          source_document_id: 11,
          canonical_source_id: 'contract-na',
          title: 'National Agreement',
          source_type: 'CONTRACT',
          source_type_label: 'National Agreement',
          is_current: true,
          processing_status: 'processed',
          is_indexed: true,
          chunk_count: 10,
          embedded_chunk_count: 10,
          authority_notice: AUTHORITY_NOTICE,
        })
      }
      if (url.includes('/research/sources') && method === 'GET') {
        return jsonResponse({
          count: 0,
          total: 0,
          limit: 50,
          offset: 0,
          sources: [],
          authority_notice: AUTHORITY_NOTICE,
        })
      }
      if (url.includes('/research/passages/') && method === 'GET') {
        return jsonResponse({
          source_chunk_id: 101,
          chunk_index: 3,
          source_document_id: 11,
          canonical_source_id: 'contract-na',
          source_title: 'National Agreement Article Text',
          source_type: 'CONTRACT',
          source_type_label: 'National Agreement',
          page_number: 12,
          section_label: 'Overtime',
          passage_text: 'Article 16 governs overtime assignments for regulars.',
          metadata: { article: '16', section: 'Overtime', page: 12 },
          processing_status: 'processed',
          is_indexed: true,
          authority_notice: AUTHORITY_NOTICE,
        })
      }
      if (url.includes('/research/search') && method === 'POST') {
        searchCount += 1
        const body = init?.body
          ? (JSON.parse(String(init.body)) as Record<string, unknown>)
          : {}
        searchBodies.push(body)
        if (options.delayMs) {
          await new Promise((resolve) => setTimeout(resolve, options.delayMs))
        }
        if (options.searchStatus && options.searchStatus >= 400) {
          return jsonResponse(
            {
              detail:
                options.searchErrorDetail ??
                'Retrieval is temporarily unavailable.',
            },
            options.searchStatus,
          )
        }
        const response =
          typeof options.searchResponse === 'function'
            ? options.searchResponse()
            : (options.searchResponse ?? makeSearchResponse())
        return jsonResponse(response)
      }

      return jsonResponse({ detail: `Unhandled mock: ${method} ${url}` }, 404)
    },
    {
      autoEmptyMessages: false,
      autoEmptyArtifacts: false,
    },
  )

  return {
    fetchMock,
    searchBodies,
    requestUrls,
    requestHeaders,
    sourcesCalls,
    mutationCalls,
    get searchCount() {
      return searchCount
    },
    get metaCount() {
      return metaCount
    },
  }
}

describe('W6 M9 Sources Research', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
    vi.restoreAllMocks()
  })

  it('renders Sources Research under the workspace with existing navigation', async () => {
    researchHandler()
    renderApp({
      initialEntries: [`/cases/${SAMPLE_CASE_UUID}/research`],
    })

    const panel = await screen.findByTestId('sources-research-panel')
    expect(
      within(panel).getByRole('heading', { name: 'Sources Research' }),
    ).toBeInTheDocument()
    expect(screen.getAllByRole('heading', { level: 1 })).toHaveLength(1)
    expect(screen.getByRole('heading', { level: 1 })).toHaveFocus()
    const nav = screen.getByRole('navigation', {
      name: 'Case workspace sections',
    })
    for (const label of [
      'Conversation',
      'Evidence',
      'Analysis',
      'Grievance',
      'Artifacts & History',
      'Workflow',
      'Sources Research',
    ]) {
      expect(within(nav).getByRole('link', { name: label })).toBeTruthy()
    }
  })

  it('announces metadata failure safely and retries filter loading', async () => {
    const user = userEvent.setup()
    const api = researchHandler({ metaFailures: 1 })
    renderApp({
      initialEntries: [`/cases/${SAMPLE_CASE_UUID}/research`],
    })

    const panel = await screen.findByTestId('sources-research-panel')
    const alert = await within(panel).findByRole('alert')
    expect(alert).toHaveTextContent(/server error/i)
    expect(alert).not.toHaveTextContent(/psycopg|database\.py|C:\\/i)
    await user.click(within(alert).getByRole('button', { name: 'Retry' }))

    expect(
      await within(panel).findByRole('option', { name: 'National Agreement' }),
    ).toBeInTheDocument()
    expect(api.metaCount).toBe(2)
  })

  it('shows authority-versus-evidence distinction and no mutation controls', async () => {
    researchHandler()
    renderApp({
      initialEntries: [`/cases/${SAMPLE_CASE_UUID}/research`],
    })
    const panel = await screen.findByTestId('sources-research-panel')
    expect(within(panel).getByTestId('authority-evidence-notice')).toHaveTextContent(
      /indexed authority corpus/i,
    )
    expect(within(panel).queryByRole('button', { name: /ingest/i })).toBeNull()
    expect(within(panel).queryByRole('button', { name: /delete/i })).toBeNull()
    expect(within(panel).queryByRole('button', { name: /re-?embed/i })).toBeNull()
    expect(within(panel).queryByRole('button', { name: /reprocess/i })).toBeNull()
    expect(panel.textContent).not.toMatch(/GRIEVANCEHUB_API_KEY|sk-[a-zA-Z0-9]+/)
  })

  it('searches via browser-safe research endpoint without API key or /sources', async () => {
    const user = userEvent.setup()
    const api = researchHandler()
    renderApp({
      initialEntries: [`/cases/${SAMPLE_CASE_UUID}/research`],
    })
    const panel = await screen.findByTestId('sources-research-panel')

    await user.type(within(panel).getByLabelText('Query'), 'overtime article 16')
    await user.selectOptions(
      within(panel).getByLabelText('Source type'),
      'CONTRACT',
    )
    fireEvent.change(within(panel).getByLabelText('Result limit'), {
      target: { value: '5' },
    })
    await user.click(within(panel).getByRole('button', { name: 'Search' }))

    await within(panel).findByText(/National Agreement Article Text/)
    expect(api.sourcesCalls).toHaveLength(0)
    expect(api.searchCount).toBe(1)
    expect(api.searchBodies[0]).toMatchObject({
      query: 'overtime article 16',
      source_types: ['CONTRACT'],
      limit: 5,
      offset: 0,
    })
    const searchCall = api.requestUrls.find((item) =>
      item.includes('/research/search'),
    )
    expect(searchCall).toMatch(/^POST /)
    expect(searchCall).not.toMatch(/\/sources\//)
    for (const headers of api.requestHeaders) {
      const serialized = JSON.stringify(headers).toLowerCase()
      expect(serialized).not.toContain('x-api-key')
      expect(serialized).not.toContain('grievancehub')
      expect(serialized).not.toContain('bearer ')
    }
    expect(api.mutationCalls).toHaveLength(0)
  })

  it('restores URL-backed search state on direct navigation', async () => {
    researchHandler()
    renderApp({
      initialEntries: [
        `/cases/${SAMPLE_CASE_UUID}/research?q=overtime&sourceType=CONTRACT&limit=5`,
      ],
    })
    const panel = await screen.findByTestId('sources-research-panel')
    expect(within(panel).getByLabelText('Query')).toHaveValue('overtime')
    await within(panel).findByText(/National Agreement Article Text/)
    expect(within(panel).getByLabelText('Source type')).toHaveValue('CONTRACT')
  })

  it('renders empty and failed retrieval states distinctly', async () => {
    const user = userEvent.setup()
    researchHandler({
      searchResponse: makeSearchResponse({
        retrieval_status: 'empty',
        retrieval_status_raw: 'no_relevant_results',
        result_count: 0,
        total_matched: 0,
        results: [],
      }),
    })
    const view = renderApp({
      initialEntries: [`/cases/${SAMPLE_CASE_UUID}/research`],
    })
    const panel = await screen.findByTestId('sources-research-panel')
    await user.type(within(panel).getByLabelText('Query'), 'zzzz')
    await user.click(within(panel).getByRole('button', { name: 'Search' }))
    expect(
      await within(panel).findByText(/No matching authority passages/i),
    ).toBeInTheDocument()
    view.unmount()
    vi.unstubAllGlobals()

    const user2 = userEvent.setup()
    researchHandler({
      searchStatus: 503,
      searchErrorDetail: 'Retrieval is temporarily unavailable.',
    })
    renderApp({
      initialEntries: [`/cases/${SAMPLE_CASE_UUID}/research`],
    })
    const panel2 = await screen.findByTestId('sources-research-panel')
    await user2.type(within(panel2).getByLabelText('Query'), 'overtime')
    await user2.click(within(panel2).getByRole('button', { name: 'Search' }))
    expect(await within(panel2).findByRole('alert')).toHaveTextContent(
      /server error|unable to complete/i,
    )
  })

  it('opens and closes read-only passage detail without secrets', async () => {
    const user = userEvent.setup()
    researchHandler()
    renderApp({
      initialEntries: [`/cases/${SAMPLE_CASE_UUID}/research?q=overtime`],
    })
    const panel = await screen.findByTestId('sources-research-panel')
    await within(panel).findByText(/Article 16 governs overtime/)
    const resultButton = within(panel).getByRole('button', {
      name: /National Agreement Article Text/i,
    })
    await user.click(resultButton)
    const dialog = await screen.findByRole('dialog')
    expect(dialog).toHaveTextContent(/Read-only authority passage/i)
    expect(dialog).toHaveTextContent(/Article 16 governs overtime/)
    expect(dialog.textContent).not.toMatch(
      /embedding|local_path|postgresql|sk-/i,
    )
    const close = within(dialog).getByRole('button', { name: 'Close' })
    expect(close).toHaveFocus()
    await user.tab()
    expect(close).toHaveFocus()
    await user.keyboard('{Escape}')
    await waitFor(() => {
      expect(screen.queryByRole('dialog')).toBeNull()
    })
    expect(resultButton).toHaveFocus()
  })

  it('prevents duplicate pending submissions', async () => {
    const user = userEvent.setup()
    const api = researchHandler({ delayMs: 250 })
    renderApp({
      initialEntries: [`/cases/${SAMPLE_CASE_UUID}/research`],
    })
    const panel = await screen.findByTestId('sources-research-panel')
    await user.type(within(panel).getByLabelText('Query'), 'overtime')
    const searchButton = within(panel).getByRole('button', { name: 'Search' })
    await user.click(searchButton)
    expect(searchButton).toBeDisabled()
    await waitFor(() => {
      expect(api.searchCount).toBe(1)
    })
    await within(panel).findByText(/National Agreement Article Text/)
  })

  it('clears selection and search state when switching cases', async () => {
    researchHandler()
    const view = renderApp({
      initialEntries: [
        `/cases/${SAMPLE_CASE_UUID}/research?q=overtime&chunk=101`,
      ],
    })
    await screen.findByRole('dialog')
    await view.router.navigate(`/cases/${OTHER_CASE_UUID}/research`)
    await waitFor(() => {
      expect(view.router.state.location.pathname).toBe(
        `/cases/${OTHER_CASE_UUID}/research`,
      )
      expect(view.router.state.location.search).toBe('')
    })
    await waitFor(() => {
      expect(screen.queryByRole('dialog')).toBeNull()
    })
    await waitFor(() => {
      const panel = screen.getByTestId('sources-research-panel')
      expect(within(panel).getByLabelText('Query')).toHaveValue('')
      expect(
        within(panel).queryByText(/Article 16 governs overtime/),
      ).toBeNull()
    })
  })

  it('does not call protected sources when browsing research', async () => {
    const api = researchHandler()
    renderApp({
      initialEntries: [`/cases/${SAMPLE_CASE_UUID}/research?q=overtime`],
    })
    const panel = await screen.findByTestId('sources-research-panel')
    await within(panel).findByText(/National Agreement Article Text/)
    expect(api.sourcesCalls).toHaveLength(0)
    expect(api.requestUrls.every((url) => !url.includes('/sources'))).toBe(
      true,
    )
  })

  it('keeps Conversation, Artifacts, and Workflow routes loadable', async () => {
    const user = userEvent.setup()
    const api = researchHandler()
    renderApp({
      initialEntries: [`/cases/${SAMPLE_CASE_UUID}/research`],
    })
    await screen.findByTestId('sources-research-panel')
    const nav = screen.getByRole('navigation', {
      name: 'Case workspace sections',
    })
    await user.click(within(nav).getByRole('link', { name: 'Conversation' }))
    await waitFor(() => {
      expect(
        api.requestUrls.some((url) => url.includes('/messages')),
      ).toBe(true)
    })
    await user.click(
      within(nav).getByRole('link', { name: 'Artifacts & History' }),
    )
    await waitFor(() => {
      expect(
        api.requestUrls.some((url) => url.includes('/artifacts')),
      ).toBe(true)
    })
    await user.click(within(nav).getByRole('link', { name: 'Workflow' }))
    await waitFor(() => {
      expect(
        api.requestUrls.some((url) => url.includes('/workflow')),
      ).toBe(true)
    })
  })

  it('Clear resets URL-backed filters', async () => {
    const user = userEvent.setup()
    researchHandler()
    const view = renderApp({
      initialEntries: [
        `/cases/${SAMPLE_CASE_UUID}/research?q=overtime&sourceType=CONTRACT`,
      ],
    })
    const panel = await screen.findByTestId('sources-research-panel')
    expect(within(panel).getByLabelText('Query')).toHaveValue('overtime')
    await user.click(within(panel).getByRole('button', { name: 'Clear' }))
    await waitFor(() => {
      expect(view.router.state.location.search).not.toContain('q=')
    })
    expect(within(panel).getByLabelText('Query')).toHaveValue('')
  })
})
