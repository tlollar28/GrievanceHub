import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'
import {
  OTHER_CASE_UUID,
  SAMPLE_ANALYSIS_ARTIFACT_UUID,
  SAMPLE_ANALYSIS_ARTIFACT_UUID_V2,
  SAMPLE_CASE_UUID,
  SAMPLE_GRIEVANCE_ARTIFACT_UUID,
  SAMPLE_HISTORY_EVENT_ID,
  binaryResponse,
  installApiMock,
  jsonResponse,
  makeAnalysisArtifactDetail,
  makeAnalysisArtifactSummary,
  makeArtifactListResponse,
  makeCompareResponse,
  makeGrievanceArtifactDetail,
  makeGrievanceArtifactSummary,
  makeHistoryContextResponse,
  makeHistoryItem,
  makeHistoryResponse,
  makeTimelineEvent,
  makeTimelineResponse,
  makeWorkspace,
} from './savedCasesFixtures'
import { renderApp } from './testUtils'

type HandlerOptions = {
  artifacts?: ReturnType<typeof makeAnalysisArtifactSummary>[]
  otherArtifacts?: ReturnType<typeof makeAnalysisArtifactSummary>[]
  history?: ReturnType<typeof makeHistoryItem>[]
  timeline?: ReturnType<typeof makeTimelineEvent>[]
  contextError?: boolean
  compareErrorDetail?: string
  listError?: boolean
  pdfStatus?: number
  detailExtra?: Record<string, unknown>
}

function artifactsHandler(options: HandlerOptions = {}) {
  const artifacts =
    options.artifacts ??
    [
      makeAnalysisArtifactSummary(),
      makeGrievanceArtifactSummary(),
      makeAnalysisArtifactSummary({
        artifact_uuid: SAMPLE_ANALYSIS_ARTIFACT_UUID_V2,
        title: 'Analysis Report v2',
        version_number: 2,
        version_label: 'v2',
        saved_at: '2026-07-25T10:00:00Z',
        key_summary: {
          primary_issue: 'Denied overtime — revised',
          confidence: 'high',
        },
      }),
    ]
  const otherArtifacts =
    options.otherArtifacts ??
    [
      makeAnalysisArtifactSummary({
        case_uuid: OTHER_CASE_UUID,
        artifact_uuid: 'other-analysis-artifact',
        title: 'Other case analysis',
      }),
    ]
  const history = options.history ?? [
    makeHistoryItem({
      event_id: SAMPLE_HISTORY_EVENT_ID,
      event_timestamp: '2026-07-25T10:00:00Z',
      title: 'Newer official save',
    }),
    makeHistoryItem({
      event_id: 'evt-older',
      event_timestamp: '2026-07-24T20:00:00Z',
      title: 'Older official save',
      artifact_uuid: SAMPLE_GRIEVANCE_ARTIFACT_UUID,
      artifact_type: 'grievance_form',
    }),
  ]
  const timeline = options.timeline ?? [
    makeTimelineEvent({
      event_id: 'tl-2',
      event_timestamp: '2026-07-24T20:00:00Z',
      event_type: 'analysis_report_saved_and_printed',
      title: 'Analysis saved',
    }),
    makeTimelineEvent({
      event_id: 'tl-1',
      event_timestamp: '2026-07-01T12:00:00Z',
      event_type: 'case_created',
      title: 'Case created',
    }),
  ]

  const compareCalls: Array<Record<string, unknown>> = []
  const pdfCalls: string[] = []
  const mutationPosts: string[] = []
  const sourcesCalls: string[] = []
  const outcomeCalls: string[] = []

  const fetchMock = installApiMock((input, init) => {
    const url = String(input)
    const method = init?.method ?? 'GET'

    if (url.includes('/sources')) {
      sourcesCalls.push(`${method} ${url}`)
      return jsonResponse({ detail: 'Forbidden in M7 tests' }, 500)
    }
    if (url.includes('/outcomes') || url.includes('/workflow/transitions')) {
      outcomeCalls.push(`${method} ${url}`)
      return jsonResponse({ detail: 'Forbidden in M7 tests' }, 500)
    }
    if (
      method === 'POST' &&
      (url.includes('/reports/') ||
        url.includes('/grievances/') ||
        url.includes('/actions') ||
        url.includes('/interactions') ||
        url.includes('/assets'))
    ) {
      mutationPosts.push(`${method} ${url}`)
    }

    if (url.includes(`/cases/${SAMPLE_CASE_UUID}/workspace`)) {
      return jsonResponse(makeWorkspace())
    }
    if (url.includes(`/cases/${OTHER_CASE_UUID}/workspace`)) {
      return jsonResponse(
        makeWorkspace({
          case_uuid: OTHER_CASE_UUID,
          title: 'Other case',
        }),
      )
    }

    if (
      url.includes('/artifacts/compare') &&
      method === 'POST'
    ) {
      const body = init?.body
        ? (JSON.parse(String(init.body)) as Record<string, unknown>)
        : {}
      compareCalls.push(body)
      const left = String(body.left_artifact_uuid ?? '')
      const right = String(body.right_artifact_uuid ?? '')
      if (left && right && left === right) {
        return jsonResponse(
          { detail: 'Compared artifacts must be distinct.' },
          400,
        )
      }
      const leftItem = artifacts.find((a) => a.artifact_uuid === left)
      const rightItem = artifacts.find((a) => a.artifact_uuid === right)
      if (
        leftItem &&
        rightItem &&
        leftItem.artifact_type !== rightItem.artifact_type
      ) {
        return jsonResponse(
          {
            detail:
              'Compared artifacts must share the same artifact_type.',
          },
          400,
        )
      }
      if (options.compareErrorDetail) {
        return jsonResponse({ detail: options.compareErrorDetail }, 400)
      }
      return jsonResponse(makeCompareResponse())
    }

    if (/\/history\/[^/]+\/context/.test(url) && method === 'GET') {
      if (options.contextError) {
        return jsonResponse({ detail: 'Context unavailable' }, 404)
      }
      const match = url.match(/\/history\/([^/]+)\/context/)
      const eventId = match?.[1] ?? SAMPLE_HISTORY_EVENT_ID
      return jsonResponse(
        makeHistoryContextResponse({ event_id: decodeURIComponent(eventId) }),
      )
    }

    if (/\/cases\/saved\/[^/]+\/history/.test(url) && method === 'GET') {
      const match = url.match(/\/cases\/saved\/([^/]+)\/history/)
      const caseUuid = match?.[1] ?? SAMPLE_CASE_UUID
      const order = new URL(url, 'http://local').searchParams.get('order')
      const events =
        order === 'oldest_first' ? [...history].reverse() : [...history]
      return jsonResponse(
        makeHistoryResponse(events, {
          case_uuid: caseUuid,
          order:
            order === 'oldest_first' ? 'oldest_first' : 'newest_first',
        }),
      )
    }

    if (/\/cases\/saved\/[^/]+\/timeline/.test(url) && method === 'GET') {
      const match = url.match(/\/cases\/saved\/([^/]+)\/timeline/)
      const caseUuid = match?.[1] ?? SAMPLE_CASE_UUID
      const order = new URL(url, 'http://local').searchParams.get('order')
      const events =
        order === 'oldest_first' ? [...timeline].reverse() : [...timeline]
      return jsonResponse(
        makeTimelineResponse(events, {
          case_uuid: caseUuid,
          order:
            order === 'oldest_first' ? 'oldest_first' : 'newest_first',
        }),
      )
    }

    if (
      /\/cases\/[^/]+\/artifacts\/[^/]+\/pdf/.test(url) &&
      method === 'GET'
    ) {
      pdfCalls.push(url)
      if (options.pdfStatus === 404) {
        return jsonResponse({ detail: 'PDF not found' }, 404)
      }
      return binaryResponse('%PDF-1.4-m7', 'application/pdf', 200)
    }

    if (
      /\/cases\/[^/]+\/artifacts\/[^/?]+$/.test(url.split('?')[0] ?? url) &&
      method === 'GET'
    ) {
      const match = url.match(/\/artifacts\/([^/?]+)/)
      const artifactUuid = match?.[1] ?? ''
      const found =
        artifacts.find((a) => a.artifact_uuid === artifactUuid) ??
        otherArtifacts.find((a) => a.artifact_uuid === artifactUuid)
      if (!found) {
        return jsonResponse({ detail: 'Artifact not found' }, 404)
      }
      if (found.artifact_type === 'grievance_form') {
        return jsonResponse(
          makeGrievanceArtifactDetail({
            ...found,
            ...options.detailExtra,
          }),
        )
      }
      return jsonResponse(
        makeAnalysisArtifactDetail({
          ...found,
          ...options.detailExtra,
        }),
      )
    }

    if (/\/cases\/[^/]+\/artifacts/.test(url) && method === 'GET') {
      if (options.listError) {
        return jsonResponse({ detail: 'Artifact list failed' }, 500)
      }
      const match = url.match(/\/cases\/([^/]+)\/artifacts/)
      const caseUuid = match?.[1] ?? SAMPLE_CASE_UUID
      const type = new URL(url, 'http://local').searchParams.get(
        'artifact_type',
      )
      const pool = caseUuid === OTHER_CASE_UUID ? otherArtifacts : artifacts
      const filtered = type
        ? pool.filter((item) => item.artifact_type === type)
        : pool
      return jsonResponse(
        makeArtifactListResponse(filtered, { case_uuid: caseUuid }),
      )
    }

    throw new Error(`Unexpected fetch: ${method} ${url}`)
  })

  return {
    fetchMock,
    compareCalls,
    pdfCalls,
    mutationPosts,
    sourcesCalls,
    outcomeCalls,
  }
}

describe('W6 M7 Artifacts & History', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
    vi.restoreAllMocks()
  })

  it('renders Artifacts & History within the workspace and supports direct navigation', async () => {
    artifactsHandler()
    const { router } = renderApp({
      initialEntries: [`/cases/${SAMPLE_CASE_UUID}/artifacts`],
    })

    expect(
      await screen.findByRole('heading', { name: 'Artifacts & History' }),
    ).toBeInTheDocument()
    expect(
      screen.getByRole('navigation', { name: 'Case workspace sections' }),
    ).toBeInTheDocument()
    expect(
      screen.getByRole('link', { name: 'Artifacts & History' }),
    ).toHaveAttribute('aria-current', 'page')
    expect(router.state.location.pathname).toBe(
      `/cases/${SAMPLE_CASE_UUID}/artifacts`,
    )
    expect(
      screen.getByRole('link', { name: 'Conversation' }),
    ).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Evidence' })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Analysis' })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Grievance' })).toBeInTheDocument()
  })

  it('restores artifact and history data on refresh (remount)', async () => {
    artifactsHandler()
    const first = renderApp({
      initialEntries: [`/cases/${SAMPLE_CASE_UUID}/artifacts`],
    })
    expect(await screen.findByText('Analysis Report v1')).toBeInTheDocument()
    expect(await screen.findByText('Newer official save')).toBeInTheDocument()
    first.unmount()

    renderApp({
      initialEntries: [`/cases/${SAMPLE_CASE_UUID}/artifacts`],
    })
    expect(await screen.findByText('Analysis Report v1')).toBeInTheDocument()
    expect(await screen.findByText('Newer official save')).toBeInTheDocument()
    expect(await screen.findByText('Analysis saved')).toBeInTheDocument()
  })

  it('renders analysis and grievance artifacts and filters by type', async () => {
    const user = userEvent.setup()
    artifactsHandler()
    renderApp({
      initialEntries: [`/cases/${SAMPLE_CASE_UUID}/artifacts`],
    })

    expect(await screen.findByText('Analysis Report v1')).toBeInTheDocument()
    expect(
      screen.getByText('Official Grievance Worksheet — Step 1 v1'),
    ).toBeInTheDocument()

    await user.selectOptions(
      screen.getByLabelText('Artifact type'),
      'analysis_report',
    )
    await waitFor(() => {
      expect(
        screen.queryByText('Official Grievance Worksheet — Step 1 v1'),
      ).not.toBeInTheDocument()
    })
    expect(screen.getByText('Analysis Report v1')).toBeInTheDocument()
  })

  it('opens read-only artifact detail and never displays stored_path', async () => {
    const user = userEvent.setup()
    artifactsHandler()
    renderApp({
      initialEntries: [`/cases/${SAMPLE_CASE_UUID}/artifacts`],
    })

    await user.click(await screen.findByText('Analysis Report v1'))
    expect(
      await screen.findByText('Read-only saved artifact. Opening this view does not regenerate or edit the record.'),
    ).toBeInTheDocument()
    expect(screen.getByText(/Denied overtime appears grievable/i)).toBeInTheDocument()
    expect(screen.queryByText(/secret\/storage/i)).not.toBeInTheDocument()
    expect(screen.queryByText('stored_path')).not.toBeInTheDocument()
    const detail = screen.getByRole('heading', { name: 'Artifact detail' })
      .closest('section')
    expect(detail).toBeTruthy()
    expect(
      within(detail as HTMLElement).queryByRole('button', {
        name: /edit artifact|generate analysis|generate grievance|save and print/i,
      }),
    ).not.toBeInTheDocument()
  })

  it('loads PDF through the binary artifact route and handles unavailable PDF', async () => {
    const user = userEvent.setup()
    const { pdfCalls } = artifactsHandler()
    const { unmount } = renderApp({
      initialEntries: [
        `/cases/${SAMPLE_CASE_UUID}/artifacts?artifact=${SAMPLE_ANALYSIS_ARTIFACT_UUID}`,
      ],
    })

    await user.click(await screen.findByRole('button', { name: 'Preview PDF' }))
    await waitFor(() => {
      expect(pdfCalls.some((url) => url.includes('/artifacts/') && url.endsWith('/pdf'))).toBe(
        true,
      )
    })
    expect(
      await screen.findByTitle('Analysis Report v1'),
    ).toBeInTheDocument()
    unmount()

    artifactsHandler({
      artifacts: [
        makeAnalysisArtifactSummary({ pdf_status: 'failed' }),
      ],
      pdfStatus: 404,
    })
    renderApp({
      initialEntries: [
        `/cases/${SAMPLE_CASE_UUID}/artifacts?artifact=${SAMPLE_ANALYSIS_ARTIFACT_UUID}`,
      ],
    })
    await user.click(await screen.findByRole('button', { name: 'Preview PDF' }))
    expect(
      await screen.findByRole('alert'),
    ).toHaveTextContent(/PDF preparation failed|not available/i)
  })

  it('renders history in order and timeline data', async () => {
    artifactsHandler()
    renderApp({
      initialEntries: [`/cases/${SAMPLE_CASE_UUID}/artifacts`],
    })

    const historyList = await screen.findByLabelText(
      'Official Case Record events',
    )
    const historyItems = within(historyList).getAllByRole('listitem')
    expect(historyItems[0]).toHaveTextContent('Newer official save')
    expect(historyItems[1]).toHaveTextContent('Older official save')

    const timelineList = await screen.findByLabelText('Case timeline events')
    expect(within(timelineList).getByText('Analysis saved')).toBeInTheDocument()
    expect(within(timelineList).getByText('Case created')).toBeInTheDocument()
  })

  it('loads jump-to-context as a read-only dialog', async () => {
    const user = userEvent.setup()
    const { mutationPosts } = artifactsHandler()
    renderApp({
      initialEntries: [`/cases/${SAMPLE_CASE_UUID}/artifacts`],
    })

    const jumpButtons = await screen.findAllByRole('button', {
      name: 'Jump to context',
    })
    await user.click(jumpButtons[0]!)

    const dialog = await screen.findByRole('dialog', { name: 'Jump to context' })
    expect(
      within(dialog).getByText(/Read-only historical context/i),
    ).toBeInTheDocument()
    expect(
      within(dialog).getByText('Can we grieve denied overtime?'),
    ).toBeInTheDocument()
    expect(
      within(dialog).queryByRole('button', { name: /generate|save|send/i }),
    ).not.toBeInTheDocument()
    expect(mutationPosts).toHaveLength(0)

    await user.keyboard('{Escape}')
    await waitFor(() => {
      expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
    })
  })

  it('compares two compatible artifacts and blocks same-artifact comparison', async () => {
    const user = userEvent.setup()
    const { compareCalls } = artifactsHandler()
    const { canCompareArtifacts } = await import(
      '../features/artifacts/artifactLibraryFilters'
    )
    const same = makeAnalysisArtifactSummary()
    const sameResult = canCompareArtifacts(same, same)
    expect(sameResult.ok).toBe(false)
    if (!sameResult.ok) {
      expect(sameResult.reason).toMatch(/cannot be compared to itself/i)
    }

    renderApp({
      initialEntries: [`/cases/${SAMPLE_CASE_UUID}/artifacts`],
    })

    const analysisV1 = await screen.findByRole('checkbox', {
      name: /Select Analysis Report v1 for comparison/i,
    })
    await user.click(analysisV1)
    // Toggle same checkbox again clears selection — UI never sets left===right.
    await user.click(analysisV1)
    expect(
      screen.getByRole('button', { name: 'Compare selected' }),
    ).toBeDisabled()

    await user.click(analysisV1)
    const analysisV2 = screen.getByRole('checkbox', {
      name: /Select Analysis Report v2 for comparison/i,
    })
    await user.click(analysisV2)
    await user.click(screen.getByRole('button', { name: 'Compare selected' }))

    await waitFor(() => {
      expect(compareCalls.length).toBe(1)
    })
    expect(compareCalls[0]).toMatchObject({
      left_artifact_uuid: SAMPLE_ANALYSIS_ARTIFACT_UUID,
      right_artifact_uuid: SAMPLE_ANALYSIS_ARTIFACT_UUID_V2,
    })
    expect(
      await screen.findByText(/creates no new artifact/i),
    ).toBeInTheDocument()
    expect(screen.getByText('Changed summary keys')).toBeInTheDocument()
    expect(screen.getByText('primary_issue')).toBeInTheDocument()
  })

  it('handles incompatible comparison safely without creating artifacts', async () => {
    const user = userEvent.setup()
    const { compareCalls, mutationPosts } = artifactsHandler()
    renderApp({
      initialEntries: [`/cases/${SAMPLE_CASE_UUID}/artifacts`],
    })

    await user.click(
      await screen.findByRole('checkbox', {
        name: /Select Analysis Report v1 for comparison/i,
      }),
    )
    await user.click(
      screen.getByRole('checkbox', {
        name: /Select Official Grievance Worksheet/i,
      }),
    )
    expect(
      screen.getByText(/must share the same type/i),
    ).toBeInTheDocument()
    expect(
      screen.getByRole('button', { name: 'Compare selected' }),
    ).toBeDisabled()
    expect(compareCalls).toHaveLength(0)
    expect(mutationPosts).toHaveLength(0)
  })

  it('clears selections/dialogs on case switch and does not leak prior case data', async () => {
    const user = userEvent.setup()
    artifactsHandler()
    const { router } = renderApp({
      initialEntries: [`/cases/${SAMPLE_CASE_UUID}/artifacts`],
    })

    await user.click(
      await screen.findByRole('checkbox', {
        name: /Select Analysis Report v1 for comparison/i,
      }),
    )
    const jumpButtons = await screen.findAllByRole('button', {
      name: 'Jump to context',
    })
    await user.click(jumpButtons[0]!)
    expect(await screen.findByRole('dialog')).toBeInTheDocument()

    await router.navigate(`/cases/${OTHER_CASE_UUID}/artifacts`)

    await waitFor(() => {
      expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
    })
    expect(await screen.findByText('Other case analysis')).toBeInTheDocument()
    expect(screen.queryByText('Analysis Report v1')).not.toBeInTheDocument()
    expect(
      screen.getByRole('button', { name: 'Compare selected' }),
    ).toBeDisabled()
  })

  it('normalizes API errors and exposes accessible loading/empty states', async () => {
    artifactsHandler({ listError: true })
    renderApp({
      initialEntries: [`/cases/${SAMPLE_CASE_UUID}/artifacts`],
    })
    expect(await screen.findByRole('alert')).toHaveTextContent(
      /Artifact list failed|server error|rejected/i,
    )

    vi.unstubAllGlobals()
    artifactsHandler({ artifacts: [] })
    renderApp({
      initialEntries: [`/cases/${SAMPLE_CASE_UUID}/artifacts`],
    })
    expect(
      await screen.findByText(/No official saved artifacts/i),
    ).toBeInTheDocument()
  })

  it('does not expose M8 outcomes, Step 3 forms, or Sources admin/API keys', async () => {
    const { sourcesCalls, outcomeCalls } = artifactsHandler()
    renderApp({
      initialEntries: [`/cases/${SAMPLE_CASE_UUID}/artifacts`],
    })

    expect(
      await screen.findByRole('heading', { name: 'Artifacts & History' }),
    ).toBeInTheDocument()
    expect(
      screen.queryByRole('button', {
        name: /close case|settle case|archive case|record appeal/i,
      }),
    ).not.toBeInTheDocument()
    expect(screen.queryByText(/step 3 grievance|official step 3/i)).not.toBeInTheDocument()
    expect(
      screen.queryByRole('link', { name: /^Sources$/i }),
    ).not.toBeInTheDocument()
    expect(screen.queryByLabelText(/api key/i)).not.toBeInTheDocument()
    expect(sourcesCalls).toHaveLength(0)
    expect(outcomeCalls).toHaveLength(0)
    expect(document.body.textContent).not.toMatch(/GRIEVANCEHUB_API_KEY|sk-[a-zA-Z0-9]/)
  })

  it('keeps Conversation / Evidence / Analysis / Grievance nav intact (M3–M6)', async () => {
    artifactsHandler()
    renderApp({
      initialEntries: [`/cases/${SAMPLE_CASE_UUID}/artifacts`],
    })
    const nav = await screen.findByRole('navigation', {
      name: 'Case workspace sections',
    })
    expect(within(nav).getByRole('link', { name: 'Conversation' })).toHaveAttribute(
      'href',
      `/cases/${SAMPLE_CASE_UUID}/conversation`,
    )
    expect(within(nav).getByRole('link', { name: 'Evidence' })).toHaveAttribute(
      'href',
      `/cases/${SAMPLE_CASE_UUID}/evidence`,
    )
    expect(within(nav).getByRole('link', { name: 'Analysis' })).toHaveAttribute(
      'href',
      `/cases/${SAMPLE_CASE_UUID}/analysis`,
    )
    expect(within(nav).getByRole('link', { name: 'Grievance' })).toHaveAttribute(
      'href',
      `/cases/${SAMPLE_CASE_UUID}/grievance`,
    )
  })
})
