import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'
import {
  OTHER_CASE_UUID,
  SAMPLE_CASE_UUID,
  binaryResponse,
  installApiMock,
  jsonResponse,
  makeAnalysisPreview,
  makeGenerateResponse,
  makeReportData,
  makeSaveResponse,
  makeVersionDetail,
  makeVersionListResponse,
  makeVersionSummary,
  makeWorkspace,
} from './savedCasesFixtures'
import { renderApp } from './testUtils'

type SaveBody = {
  prepare_pdf?: boolean
  idempotency_key?: string
  preview?: unknown
  saved_by?: string
}

type HandlerOptions = {
  versions?: ReturnType<typeof makeVersionSummary>[]
  generateResponse?:
    | ReturnType<typeof makeGenerateResponse>
    | (() => Response | Promise<Response>)
  onGenerate?: (body: unknown) => void
  onSave?: (body: SaveBody) => Response | Promise<Response>
  versionsError?: boolean
  workspace?: ReturnType<typeof makeWorkspace>
  otherWorkspace?: ReturnType<typeof makeWorkspace>
}

function analysisHandler(options: HandlerOptions = {}) {
  let versions = options.versions ?? []
  const generateCalls: Array<Record<string, unknown>> = []
  const saveCalls: SaveBody[] = []
  const forbidden: string[] = []

  const fetchMock = installApiMock(
    (input, init) => {
      const url = String(input)
      const method = init?.method ?? 'GET'

      if (
        url.includes('/reports/regenerate') ||
        url.includes('/grievances/') ||
        url.includes('/sources') ||
        (url.includes('/actions') && method === 'POST')
      ) {
        forbidden.push(`${method} ${url}`)
        return jsonResponse({ detail: 'Forbidden in M5 tests' }, 500)
      }

      if (url.includes(`/cases/${SAMPLE_CASE_UUID}/workspace`)) {
        return jsonResponse(options.workspace ?? makeWorkspace())
      }
      if (url.includes(`/cases/${OTHER_CASE_UUID}/workspace`)) {
        return jsonResponse(
          options.otherWorkspace ??
            makeWorkspace({
              case_uuid: OTHER_CASE_UUID,
              title: 'Other case',
            }),
        )
      }

      if (
        /\/cases\/[^/]+\/versions\/\d+\/export\//.test(url) &&
        method === 'GET'
      ) {
        if (url.includes('/export/pdf') && !url.includes('working_draft=true')) {
          return jsonResponse(
            {
              detail:
                'Official print requires Save and Print first. Pass working_draft=true only for non-official preview.',
            },
            409,
          )
        }
        if (url.includes('/export/pdf')) {
          return binaryResponse('%PDF-1.4', 'application/pdf', 200, {
            'X-GrievanceHub-Print-Mode': 'working_draft_preview',
          })
        }
        return binaryResponse(
          '<html><body>Preview</body></html>',
          'text/html',
        )
      }

      if (
        /\/cases\/[^/]+\/versions\/\d+$/.test(url.split('?')[0] ?? url) &&
        method === 'GET'
      ) {
        const match = url.match(/\/versions\/(\d+)/)
        const versionNumber = Number(match?.[1] ?? 0)
        const caseMatch = url.match(/\/cases\/([^/]+)\/versions/)
        const caseUuid = caseMatch?.[1] ?? SAMPLE_CASE_UUID
        if (caseUuid !== SAMPLE_CASE_UUID) {
          return jsonResponse({ detail: 'Report version not found' }, 404)
        }
        const found = versions.find((v) => v.version_number === versionNumber)
        if (!found) {
          return jsonResponse({ detail: 'Report version not found' }, 404)
        }
        return jsonResponse(
          makeVersionDetail({
            ...found,
            report_data: makeReportData({
              report_title: `Saved analysis v${versionNumber}`,
            }),
          }),
        )
      }

      if (
        /\/cases\/[^/]+\/versions\/?(\?|$)/.test(url) &&
        method === 'GET'
      ) {
        if (options.versionsError) {
          return jsonResponse({ detail: 'Version list failed' }, 500)
        }
        const match = url.match(/\/cases\/([^/]+)\/versions/)
        const caseUuid = match?.[1] ?? SAMPLE_CASE_UUID
        if (caseUuid === OTHER_CASE_UUID) {
          return jsonResponse(
            makeVersionListResponse([], { case_uuid: OTHER_CASE_UUID }),
          )
        }
        return jsonResponse(
          makeVersionListResponse(versions, { case_uuid: caseUuid }),
        )
      }

      if (
        url.includes(`/cases/${SAMPLE_CASE_UUID}/reports/generate`) &&
        method === 'POST'
      ) {
        const body = JSON.parse(String(init?.body ?? '{}')) as Record<
          string,
          unknown
        >
        generateCalls.push(body)
        options.onGenerate?.(body)
        if (typeof options.generateResponse === 'function') {
          return options.generateResponse()
        }
        return jsonResponse(
          options.generateResponse ??
            makeGenerateResponse({
              preview: makeAnalysisPreview({
                suggested_version_number_if_saved: versions.length + 1,
              }),
            }),
        )
      }

      if (
        url.includes(`/cases/${SAMPLE_CASE_UUID}/reports/save-and-print`) &&
        method === 'POST'
      ) {
        const body = JSON.parse(String(init?.body ?? '{}')) as SaveBody
        saveCalls.push(body)
        if (options.onSave) {
          return options.onSave(body)
        }
        const nextVersion = versions.length + 1
        const saved = makeVersionSummary({
          id: nextVersion,
          version_number: nextVersion,
        })
        versions = [...versions, saved]
        return jsonResponse(
          makeSaveResponse({
            status: body.prepare_pdf ? 'saved' : 'saved',
            message: body.prepare_pdf
              ? 'Official analysis report saved and print package prepared.'
              : 'Official analysis report saved.',
            print_ready: Boolean(body.prepare_pdf),
            artifact: {
              artifact_uuid: 'bbbbbbbb-cccc-4ddd-8eee-ffffffffffff',
              case_uuid: SAMPLE_CASE_UUID,
              artifact_type: 'analysis_report',
              title: `Analysis Report v${nextVersion}`,
              version_number: nextVersion,
              version_label: `v${nextVersion}`,
              printed: Boolean(body.prepare_pdf),
              pdf_status: body.prepare_pdf ? 'ready' : 'pending',
              pdf_asset_uuid: body.prepare_pdf
                ? 'cccccccc-dddd-4eee-8fff-000000000000'
                : null,
              is_latest_official: true,
              saved_by: 'Steward Ada',
              saved_at: '2026-07-24T21:10:00Z',
              source_report_version_number: nextVersion,
            },
            export_path: body.prepare_pdf
              ? `/cases/${SAMPLE_CASE_UUID}/artifacts/bbbbbbbb-cccc-4ddd-8eee-ffffffffffff/pdf`
              : null,
          }),
        )
      }

      if (
        url.includes(`/cases/${SAMPLE_CASE_UUID}/artifacts/`) &&
        url.endsWith('/pdf') &&
        method === 'GET'
      ) {
        return binaryResponse('%PDF-official', 'application/pdf', 200, {
          'X-GrievanceHub-Print-Mode': 'official_saved_artifact',
        })
      }

      throw new Error(`Unexpected fetch: ${url} ${method}`)
    },
    { autoEmptyVersions: false, autoEmptyMessages: true, autoEmptyAssets: true },
  )

  return { fetchMock, generateCalls, saveCalls, forbidden, getVersions: () => versions }
}

describe('W6 M5 Analysis Generate, Preview, Save, and Print', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
    vi.restoreAllMocks()
  })

  it('restores workspace and versions on the analysis route', async () => {
    analysisHandler({
      versions: [makeVersionSummary({ version_number: 1 })],
    })
    const { router } = renderApp({
      initialEntries: [`/cases/${SAMPLE_CASE_UUID}/analysis`],
    })

    expect(
      await screen.findByRole('heading', { name: 'Analysis' }),
    ).toBeInTheDocument()
    expect(
      screen.getByRole('navigation', { name: 'Case workspace sections' }),
    ).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Analysis' })).toHaveAttribute(
      'href',
      `/cases/${SAMPLE_CASE_UUID}/analysis`,
    )
    expect(
      await screen.findByRole('button', {
        name: /Saved analysis version 1/i,
      }),
    ).toBeInTheDocument()
    expect(router.state.location.pathname).toBe(
      `/cases/${SAMPLE_CASE_UUID}/analysis`,
    )
  })

  it('supports direct navigation and browser-style refresh', async () => {
    analysisHandler({
      versions: [makeVersionSummary({ version_number: 2 })],
    })
    const first = renderApp({
      initialEntries: [`/cases/${SAMPLE_CASE_UUID}/analysis?version=2`],
    })
    expect(
      await screen.findByRole('heading', {
        name: 'Saved analysis v2',
      }),
    ).toBeInTheDocument()
    first.unmount()

    analysisHandler({
      versions: [makeVersionSummary({ version_number: 2 })],
    })
    renderApp({
      initialEntries: [`/cases/${SAMPLE_CASE_UUID}/analysis?version=2`],
    })
    expect(
      await screen.findByRole('heading', {
        name: 'Saved analysis v2',
      }),
    ).toBeInTheDocument()
  })

  it('shows loading, empty, and retryable version-list error states', async () => {
    analysisHandler({ versions: [] })
    renderApp({
      initialEntries: [`/cases/${SAMPLE_CASE_UUID}/analysis`],
    })
    expect(
      await screen.findByText(/No saved analysis versions yet/i),
    ).toBeInTheDocument()

    vi.unstubAllGlobals()
    analysisHandler({ versionsError: true })
    renderApp({
      initialEntries: [`/cases/${SAMPLE_CASE_UUID}/analysis`],
    })
    expect(await screen.findByRole('alert')).toHaveTextContent(
      /server error|Version list failed|Unable to load/i,
    )
    expect(screen.getByRole('button', { name: 'Retry' })).toBeInTheDocument()
  })

  it('does not call Generate automatically on route load', async () => {
    const { generateCalls } = analysisHandler()
    renderApp({
      initialEntries: [`/cases/${SAMPLE_CASE_UUID}/analysis`],
    })
    await screen.findByRole('heading', { name: 'Analysis' })
    await waitFor(() => {
      expect(generateCalls).toHaveLength(0)
    })
  })

  it('Generate sends the verified request and renders temporary preview', async () => {
    const user = userEvent.setup()
    const { generateCalls } = analysisHandler()
    renderApp({
      initialEntries: [`/cases/${SAMPLE_CASE_UUID}/analysis`],
    })
    await screen.findByRole('heading', { name: 'Analysis' })

    await user.click(
      screen.getByRole('button', { name: 'Generate Analysis' }),
    )

    await waitFor(() => {
      expect(generateCalls).toEqual([{ limit_per_source: 8 }])
    })
    const preview = await screen.findByLabelText('Temporary analysis preview')
    expect(
      within(preview).getByText(/Unsaved temporary preview/i),
    ).toBeInTheDocument()
    expect(
      within(preview).getAllByText('Generated analysis').length,
    ).toBeGreaterThan(0)
    expect(
      within(preview).getAllByText('Source excerpt').length,
    ).toBeGreaterThan(0)
    expect(
      within(preview).getByText(/Cancel discards this analysis/i),
    ).toBeInTheDocument()
    expect(
      screen.getByRole('button', { name: 'Generate Analysis' }),
    ).toBeDisabled()
  })

  it('prevents duplicate Generate while pending', async () => {
    const user = userEvent.setup()
    let resolveGenerate!: (value: Response) => void
    const { generateCalls } = analysisHandler({
      generateResponse: () =>
        new Promise<Response>((resolve) => {
          resolveGenerate = resolve
        }),
    })
    renderApp({
      initialEntries: [`/cases/${SAMPLE_CASE_UUID}/analysis`],
    })
    await screen.findByRole('heading', { name: 'Analysis' })
    const button = screen.getByRole('button', { name: 'Generate Analysis' })
    await user.click(button)
    await user.click(button)
    expect(generateCalls).toHaveLength(1)
    resolveGenerate(jsonResponse(makeGenerateResponse()))
    expect(
      await screen.findByLabelText('Temporary analysis preview'),
    ).toBeInTheDocument()
  })

  it('omits fake placeholders for missing optional citation fields', async () => {
    const user = userEvent.setup()
    analysisHandler({
      generateResponse: makeGenerateResponse({
        preview: makeAnalysisPreview({
          report_data: makeReportData({
            supporting_evidence: [
              {
                direct_quote: 'Quoted language only.',
              },
            ],
            key_contract_violations: [
              {
                role_title: 'Background Authority',
                why_relevant: 'Context only',
                citation: {},
              },
            ],
          }),
        }),
      }),
    })
    renderApp({
      initialEntries: [`/cases/${SAMPLE_CASE_UUID}/analysis`],
    })
    await user.click(
      await screen.findByRole('button', { name: 'Generate Analysis' }),
    )
    expect(await screen.findByText('Quoted language only.')).toBeInTheDocument()
    expect(screen.queryByText(/p\.\s*undefined/i)).not.toBeInTheDocument()
    expect(screen.queryByText(/page unknown/i)).not.toBeInTheDocument()
  })

  it('Cancel clears preview and sends no Save request', async () => {
    const user = userEvent.setup()
    const { saveCalls, getVersions } = analysisHandler()
    renderApp({
      initialEntries: [`/cases/${SAMPLE_CASE_UUID}/analysis`],
    })
    await user.click(
      await screen.findByRole('button', { name: 'Generate Analysis' }),
    )
    expect(
      await screen.findByLabelText('Temporary analysis preview'),
    ).toBeInTheDocument()

    await user.click(
      screen.getByRole('button', {
        name: 'Cancel temporary analysis preview',
      }),
    )
    await user.click(
      screen.getByRole('button', { name: 'Discard preview' }),
    )

    await waitFor(() => {
      expect(
        screen.queryByLabelText('Temporary analysis preview'),
      ).not.toBeInTheDocument()
    })
    expect(saveCalls).toHaveLength(0)
    expect(getVersions()).toHaveLength(0)
    expect(
      screen.getByText(/No saved analysis versions yet/i),
    ).toBeInTheDocument()
  })

  it('case switch clears temporary preview', async () => {
    const user = userEvent.setup()
    analysisHandler()
    const { router } = renderApp({
      initialEntries: [`/cases/${SAMPLE_CASE_UUID}/analysis`],
    })
    await user.click(
      await screen.findByRole('button', { name: 'Generate Analysis' }),
    )
    expect(
      await screen.findByLabelText('Temporary analysis preview'),
    ).toBeInTheDocument()

    await router.navigate(`/cases/${OTHER_CASE_UUID}/analysis`)
    expect(
      await screen.findByRole('heading', { name: 'Analysis' }),
    ).toBeInTheDocument()
    await waitFor(() => {
      expect(
        screen.queryByLabelText('Temporary analysis preview'),
      ).not.toBeInTheDocument()
    })
  })

  it('Save and Save and Print use verified prepare_pdf and clear preview', async () => {
    const user = userEvent.setup()
    const { saveCalls } = analysisHandler()
    renderApp({
      initialEntries: [`/cases/${SAMPLE_CASE_UUID}/analysis`],
    })
    await user.click(
      await screen.findByRole('button', { name: 'Generate Analysis' }),
    )
    await screen.findByLabelText('Temporary analysis preview')

    await user.click(screen.getByRole('button', { name: 'Save' }))
    await waitFor(() => {
      expect(saveCalls).toHaveLength(1)
    })
    expect(saveCalls[0]).toMatchObject({
      prepare_pdf: false,
      preview: expect.objectContaining({ temporary: true, persisted: false }),
      idempotency_key: expect.any(String),
    })
    await waitFor(() => {
      expect(
        screen.queryByLabelText('Temporary analysis preview'),
      ).not.toBeInTheDocument()
    })
    expect(
      await screen.findByRole('button', {
        name: /Saved analysis version 1/i,
      }),
    ).toBeInTheDocument()
    expect(screen.getByText(/Official saved version/i)).toBeInTheDocument()

    await user.click(
      screen.getByRole('button', { name: 'Generate Analysis' }),
    )
    await screen.findByLabelText('Temporary analysis preview')
    await user.click(screen.getByRole('button', { name: 'Save and Print' }))
    await waitFor(() => {
      expect(saveCalls).toHaveLength(2)
    })
    expect(saveCalls[1]).toMatchObject({
      prepare_pdf: true,
      idempotency_key: expect.any(String),
    })
    expect(saveCalls[0]?.idempotency_key).not.toEqual(
      saveCalls[1]?.idempotency_key,
    )
  })

  it('keeps idempotency key stable during save retry', async () => {
    const user = userEvent.setup()
    let attempts = 0
    const { saveCalls } = analysisHandler({
      onSave: () => {
        attempts += 1
        if (attempts === 1) {
          return jsonResponse({ detail: 'Temporary failure' }, 500)
        }
        return jsonResponse(
          makeSaveResponse({
            artifact: {
              artifact_uuid: 'bbbbbbbb-cccc-4ddd-8eee-ffffffffffff',
              case_uuid: SAMPLE_CASE_UUID,
              artifact_type: 'analysis_report',
              title: 'Analysis Report v1',
              version_number: 1,
              version_label: 'v1',
              printed: false,
              pdf_status: 'pending',
              saved_at: '2026-07-24T21:10:00Z',
              source_report_version_number: 1,
            },
          }),
        )
      },
    })
    renderApp({
      initialEntries: [`/cases/${SAMPLE_CASE_UUID}/analysis`],
    })
    await user.click(
      await screen.findByRole('button', { name: 'Generate Analysis' }),
    )
    await screen.findByLabelText('Temporary analysis preview')
    await user.click(screen.getByRole('button', { name: 'Save' }))
    expect(await screen.findByRole('alert')).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Retry save' }))
    await waitFor(() => {
      expect(saveCalls).toHaveLength(2)
    })
    expect(saveCalls[0]?.idempotency_key).toBe(saveCalls[1]?.idempotency_key)
  })

  it('shows saved_pdf_failed as saved-with-warning and handles idempotent replay', async () => {
    const user = userEvent.setup()
    analysisHandler({
      onSave: () =>
        jsonResponse(
          makeSaveResponse({
            status: 'saved_pdf_failed',
            message:
              'Official analysis report saved; PDF generation failed.',
            print_ready: false,
            pdf_error: 'weasyprint unavailable',
          }),
        ),
    })
    renderApp({
      initialEntries: [`/cases/${SAMPLE_CASE_UUID}/analysis`],
    })
    await user.click(
      await screen.findByRole('button', { name: 'Generate Analysis' }),
    )
    await user.click(await screen.findByRole('button', { name: 'Save and Print' }))
    expect(
      await screen.findByText(
        /Analysis saved successfully, but PDF generation failed/i,
      ),
    ).toBeInTheDocument()

    vi.unstubAllGlobals()
    analysisHandler({
      versions: [makeVersionSummary({ version_number: 1 })],
      onSave: () =>
        jsonResponse(
          makeSaveResponse({
            status: 'idempotent_replay',
            message:
              'Idempotent Save and Print replay; no new version created.',
          }),
        ),
    })
    renderApp({
      initialEntries: [`/cases/${SAMPLE_CASE_UUID}/analysis`],
    })
    await user.click(
      await screen.findByRole('button', { name: 'Generate Analysis' }),
    )
    await user.click(await screen.findByRole('button', { name: 'Save' }))
    expect(
      await screen.findByText(/no duplicate version was created/i),
    ).toBeInTheDocument()
  })

  it('distinguishes official vs working-draft export and maps 409', async () => {
    const user = userEvent.setup()
    const revokeSpy = vi.spyOn(URL, 'revokeObjectURL')
    const createSpy = vi
      .spyOn(URL, 'createObjectURL')
      .mockReturnValue('blob:test-analysis')

    analysisHandler({
      versions: [makeVersionSummary({ version_number: 1 })],
    })
    renderApp({
      initialEntries: [`/cases/${SAMPLE_CASE_UUID}/analysis?version=1`],
    })
    expect(
      await screen.findByRole('heading', { name: 'Saved analysis v1' }),
    ).toBeInTheDocument()

    await user.click(
      screen.getByRole('button', { name: 'Working-draft PDF' }),
    )
    expect(
      await screen.findByText(/Working-draft preview \(not official\)/i),
    ).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: 'Official PDF' }))
    expect(await screen.findByRole('alert')).toHaveTextContent(
      /Official PDF requires Save and Print/i,
    )

    await user.click(screen.getByRole('button', { name: 'Close preview' }))
    expect(revokeSpy).toHaveBeenCalled()

    createSpy.mockRestore()
    revokeSpy.mockRestore()
  })

  it('conversation and evidence routes do not call Generate or grievance endpoints', async () => {
    const { generateCalls, forbidden, fetchMock } = analysisHandler({
      versions: [makeVersionSummary()],
    })
    renderApp({
      initialEntries: [`/cases/${SAMPLE_CASE_UUID}/conversation`],
    })
    expect(
      await screen.findByRole('heading', { name: 'Conversation' }),
    ).toBeInTheDocument()
    expect(generateCalls).toHaveLength(0)

    const evidence = renderApp({
      initialEntries: [`/cases/${SAMPLE_CASE_UUID}/evidence`],
    })
    expect(
      await screen.findByRole('heading', { name: 'Evidence' }),
    ).toBeInTheDocument()
    expect(generateCalls).toHaveLength(0)
    expect(forbidden).toHaveLength(0)
    const urls = fetchMock.mock.calls.map((call) => String(call[0]))
    expect(urls.some((url) => /\/grievances\//.test(url))).toBe(false)
    expect(urls.some((url) => /\/reports\/generate/.test(url))).toBe(false)
    evidence.unmount()
  })

  it('does not introduce grievance UI on the analysis route', async () => {
    analysisHandler()
    renderApp({
      initialEntries: [`/cases/${SAMPLE_CASE_UUID}/analysis`],
    })
    await screen.findByRole('heading', { name: 'Analysis' })
    expect(
      screen.queryByRole('button', { name: /Generate Grievance/i }),
    ).not.toBeInTheDocument()
    expect(screen.queryByText(/grievance draft/i)).not.toBeInTheDocument()
  })

  it('styles generated analysis distinctly from source excerpts', async () => {
    const user = userEvent.setup()
    analysisHandler()
    renderApp({
      initialEntries: [`/cases/${SAMPLE_CASE_UUID}/analysis`],
    })
    await user.click(
      await screen.findByRole('button', { name: 'Generate Analysis' }),
    )
    const preview = await screen.findByLabelText(
      'Temporary analysis preview',
    )
    expect(
      within(preview).getAllByText('Generated analysis').length,
    ).toBeGreaterThan(0)
    expect(
      within(preview).getAllByText('Source excerpt').length,
    ).toBeGreaterThan(0)
    expect(
      within(preview).getAllByText(
        'Overtime shall be distributed equitably.',
      ).length,
    ).toBeGreaterThan(0)
    expect(
      within(preview).getAllByText('Generated analysis')[0]?.className,
    ).toMatch(/kindLabel/)
    expect(preview.querySelector('blockquote')).not.toBeNull()
    expect(preview.querySelector('[class*="generated"]')).not.toBeNull()
  })
})
