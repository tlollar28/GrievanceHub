import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'
import {
  OTHER_CASE_UUID,
  SAMPLE_CASE_UUID,
  SAMPLE_GRIEVANCE_ARTIFACT_UUID,
  binaryResponse,
  installApiMock,
  jsonResponse,
  makeGenerateGrievanceResponse,
  makeGrievanceArtifactDetail,
  makeGrievanceArtifactList,
  makeGrievanceArtifactSummary,
  makeGrievanceGeneration,
  makeGrievanceSaveResponse,
  makeStep1FieldValues,
  makeStep2FieldValues,
  makeWorkspace,
} from './savedCasesFixtures'
import { renderApp } from './testUtils'
import {
  OFFICIAL_STEP_1_TEMPLATE_ID,
  OFFICIAL_STEP_2_TEMPLATE_ID,
  SUPPORTED_GRIEVANCE_TEMPLATE_IDS,
} from '../features/grievance/templateFields'

type SaveBody = {
  prepare_pdf?: boolean
  idempotency_key?: string
  template_id?: string
  field_values?: Record<string, unknown>
  steward_override_field_ids?: string[]
  missing_required_field_ids?: string[]
  validation_status?: string
  draft_status?: string
  saved_by?: string
  grievance_step?: string
}

type HandlerOptions = {
  artifacts?: ReturnType<typeof makeGrievanceArtifactSummary>[]
  generateResponse?:
    | ReturnType<typeof makeGenerateGrievanceResponse>
    | (() => Response | Promise<Response>)
  onGenerate?: (body: unknown) => void
  onSave?: (body: SaveBody) => Response | Promise<Response>
  artifactsError?: boolean
  workspace?: ReturnType<typeof makeWorkspace>
  otherWorkspace?: ReturnType<typeof makeWorkspace>
  pdfStatus?: number
}

function grievanceHandler(options: HandlerOptions = {}) {
  let artifacts = options.artifacts ?? []
  const generateCalls: Array<Record<string, unknown>> = []
  const saveCalls: SaveBody[] = []
  const forbidden: string[] = []
  const artifactCompareCalls: string[] = []
  const sourcesCalls: string[] = []

  const fetchMock = installApiMock(
    (input, init) => {
      const url = String(input)
      const method = init?.method ?? 'GET'

      if (url.includes('/sources')) {
        sourcesCalls.push(`${method} ${url}`)
        forbidden.push(`${method} ${url}`)
        return jsonResponse({ detail: 'Forbidden in M6 tests' }, 500)
      }
      if (url.includes('/artifacts/compare')) {
        artifactCompareCalls.push(`${method} ${url}`)
        forbidden.push(`${method} ${url}`)
        return jsonResponse({ detail: 'Forbidden in M6 tests' }, 500)
      }
      if (
        url.includes('/reports/generate') ||
        (url.includes('/reports/save-and-print') && method === 'POST')
      ) {
        // Allowed only if analysis route tests call them — track but do not auto-fail.
      }

      if (url.includes(`/cases/${SAMPLE_CASE_UUID}/workspace`)) {
        return jsonResponse(
          options.workspace ??
            makeWorkspace({
              available_actions: [
                {
                  action: 'generate_grievance',
                  available: true,
                  steward_visible: true,
                },
              ],
            }),
        )
      }
      if (url.includes(`/cases/${OTHER_CASE_UUID}/workspace`)) {
        return jsonResponse(
          options.otherWorkspace ??
            makeWorkspace({
              case_uuid: OTHER_CASE_UUID,
              title: 'Other case',
              available_actions: [
                {
                  action: 'generate_grievance',
                  available: true,
                  steward_visible: true,
                },
              ],
            }),
        )
      }

      if (
        /\/cases\/[^/]+\/artifacts\/[^/]+\/pdf/.test(url) &&
        method === 'GET'
      ) {
        if (options.pdfStatus === 409) {
          return jsonResponse({ detail: 'PDF not ready' }, 409)
        }
        if (options.pdfStatus === 404) {
          return jsonResponse({ detail: 'PDF not found' }, 404)
        }
        return binaryResponse('%PDF-1.4-grievance', 'application/pdf', 200)
      }

      if (
        /\/cases\/[^/]+\/artifacts\/[^/?]+$/.test(url.split('?')[0] ?? url) &&
        method === 'GET'
      ) {
        const match = url.match(/\/artifacts\/([^/?]+)/)
        const artifactUuid = match?.[1] ?? ''
        const found = artifacts.find((a) => a.artifact_uuid === artifactUuid)
        if (!found) {
          return jsonResponse({ detail: 'Artifact not found' }, 404)
        }
        return jsonResponse(makeGrievanceArtifactDetail(found))
      }

      if (
        /\/cases\/[^/]+\/artifacts/.test(url) &&
        method === 'GET'
      ) {
        if (options.artifactsError) {
          return jsonResponse({ detail: 'Artifact list failed' }, 500)
        }
        const match = url.match(/\/cases\/([^/]+)\/artifacts/)
        const caseUuid = match?.[1] ?? SAMPLE_CASE_UUID
        if (caseUuid === OTHER_CASE_UUID) {
          return jsonResponse(
            makeGrievanceArtifactList([], { case_uuid: OTHER_CASE_UUID }),
          )
        }
        return jsonResponse(
          makeGrievanceArtifactList(artifacts, { case_uuid: caseUuid }),
        )
      }

      if (
        url.includes(`/cases/${SAMPLE_CASE_UUID}/actions`) &&
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
          options.generateResponse ?? makeGenerateGrievanceResponse(),
        )
      }

      if (
        url.includes(`/cases/${SAMPLE_CASE_UUID}/grievances/save-and-print`) &&
        method === 'POST'
      ) {
        const body = JSON.parse(String(init?.body ?? '{}')) as SaveBody
        saveCalls.push(body)
        if (options.onSave) {
          return options.onSave(body)
        }
        const next = makeGrievanceArtifactSummary({
          artifact_uuid: `dddddddd-eeee-4fff-8000-${String(artifacts.length + 1).padStart(12, '0')}`,
          version_number: artifacts.length + 1,
          version_label: `v${artifacts.length + 1}`,
          template_id: body.template_id,
          grievance_step: body.grievance_step,
          pdf_status: body.prepare_pdf ? 'ready' : 'pending',
        })
        artifacts = [...artifacts, next]
        return jsonResponse(
          makeGrievanceSaveResponse({
            status: 'saved',
            print_ready: Boolean(body.prepare_pdf),
            artifact: next,
          }),
        )
      }

      return jsonResponse({ detail: `Unhandled ${method} ${url}` }, 404)
    },
    {
      autoEmptyMessages: true,
      autoEmptyAssets: true,
      autoEmptyVersions: true,
      autoEmptyArtifacts: false,
    },
  )

  return {
    fetchMock,
    generateCalls,
    saveCalls,
    forbidden,
    artifactCompareCalls,
    sourcesCalls,
    getArtifacts: () => artifacts,
  }
}

describe('W6 M6 Grievance workspace', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
    vi.restoreAllMocks()
  })

  it('restores workspace and saved grievance state on direct navigation', async () => {
    grievanceHandler({
      artifacts: [makeGrievanceArtifactSummary()],
    })
    renderApp({
      initialEntries: [`/cases/${SAMPLE_CASE_UUID}/grievance`],
    })
    expect(
      await screen.findByRole('heading', { name: 'Grievance' }),
    ).toBeInTheDocument()
    expect(
      screen.getByRole('navigation', { name: 'Case workspace sections' }),
    ).toBeInTheDocument()
    expect(
      screen.getByRole('link', { name: 'Grievance' }),
    ).toHaveAttribute('aria-current', 'page')
    expect(
      await screen.findByRole('button', {
        name: /Official Grievance Worksheet — Step 1/i,
      }),
    ).toBeInTheDocument()
    expect(
      await screen.findByRole('heading', {
        name: /Official Grievance Worksheet — Step 1/i,
      }),
    ).toBeInTheDocument()
  })

  it('does not auto-generate on route load', async () => {
    const { generateCalls } = grievanceHandler()
    renderApp({
      initialEntries: [`/cases/${SAMPLE_CASE_UUID}/grievance`],
    })
    await screen.findByRole('button', { name: 'Generate Grievance' })
    expect(generateCalls).toHaveLength(0)
    expect(
      screen.queryByLabelText('Temporary grievance draft'),
    ).not.toBeInTheDocument()
  })

  it('Generate sends exact verified action request and renders Step 1 draft', async () => {
    const user = userEvent.setup()
    const { generateCalls } = grievanceHandler()
    renderApp({
      initialEntries: [`/cases/${SAMPLE_CASE_UUID}/grievance`],
    })
    await user.click(
      await screen.findByRole('button', { name: 'Generate Grievance' }),
    )
    await waitFor(() => {
      expect(generateCalls).toHaveLength(1)
    })
    expect(generateCalls[0]).toEqual({ action: 'generate_grievance' })
    const draft = await screen.findByLabelText('Temporary grievance draft')
    expect(
      within(draft).getByText(/Unsaved grievance draft/i),
    ).toBeInTheDocument()
    expect(
      within(draft).getByText(new RegExp(OFFICIAL_STEP_1_TEMPLATE_ID)),
    ).toBeInTheDocument()
    expect(
      within(draft).getByDisplayValue('Denied overtime for tour 2.'),
    ).toBeInTheDocument()
    expect(
      within(draft).getByLabelText(/SSN or Employee ID/i),
    ).toHaveValue('')
  })

  it('prevents duplicate Generate while pending and while draft open', async () => {
    const user = userEvent.setup()
    let resolveGenerate!: (value: Response) => void
    const pending = new Promise<Response>((resolve) => {
      resolveGenerate = resolve
    })
    const { generateCalls } = grievanceHandler({
      generateResponse: () => pending,
    })
    renderApp({
      initialEntries: [`/cases/${SAMPLE_CASE_UUID}/grievance`],
    })
    const button = await screen.findByRole('button', {
      name: 'Generate Grievance',
    })
    await user.click(button)
    await waitFor(() => {
      expect(button).toBeDisabled()
      expect(button).toHaveAttribute('aria-busy', 'true')
    })
    await user.click(button)
    expect(generateCalls).toHaveLength(1)
    resolveGenerate(jsonResponse(makeGenerateGrievanceResponse()))
    const draft = await screen.findByLabelText('Temporary grievance draft')
    expect(draft).toBeInTheDocument()
    expect(
      screen.getByRole('button', { name: 'Generate Grievance' }),
    ).toBeDisabled()
  })

  it('surfaces missing prerequisites safely', async () => {
    grievanceHandler({
      workspace: makeWorkspace({
        available_actions: [
          {
            action: 'generate_grievance',
            available: false,
            reason: 'Case must be reopened before generating a grievance.',
            missing_prerequisites: [
              {
                code: 'case_closed_requires_reopen',
                message: 'Reopen the case before generating a grievance.',
              },
            ],
          },
        ],
      }),
    })
    renderApp({
      initialEntries: [`/cases/${SAMPLE_CASE_UUID}/grievance`],
    })
    expect(
      await screen.findByText(/Case must be reopened/i),
    ).toBeInTheDocument()
    expect(
      screen.getByText(/Reopen the case before generating a grievance/i),
    ).toBeInTheDocument()
    expect(
      screen.getByRole('button', { name: 'Generate Grievance' }),
    ).toBeDisabled()
  })

  it('does not render a substitute form for unsupported templates', async () => {
    const user = userEvent.setup()
    grievanceHandler({
      generateResponse: makeGenerateGrievanceResponse({
        grievance_generation: makeGrievanceGeneration({
          template_id: 'step_3_template_deferred',
          step_type: 'step_3_appeal',
          field_values: { facts_what_happened: 'should not render' },
        }),
      }),
    })
    renderApp({
      initialEntries: [`/cases/${SAMPLE_CASE_UUID}/grievance`],
    })
    await user.click(
      await screen.findByRole('button', { name: 'Generate Grievance' }),
    )
    expect(
      await screen.findByText(/not available in the current product/i),
    ).toBeInTheDocument()
    expect(
      screen.queryByLabelText('Temporary grievance draft'),
    ).not.toBeInTheDocument()
    expect(screen.queryByDisplayValue('should not render')).not.toBeInTheDocument()
  })

  it('renders Step 2 template when supplied and accepts only Step 1/2 IDs', async () => {
    const user = userEvent.setup()
    expect(SUPPORTED_GRIEVANCE_TEMPLATE_IDS).toEqual([
      OFFICIAL_STEP_1_TEMPLATE_ID,
      OFFICIAL_STEP_2_TEMPLATE_ID,
    ])
    grievanceHandler({
      generateResponse: makeGenerateGrievanceResponse({
        grievance_generation: makeGrievanceGeneration({
          template_id: OFFICIAL_STEP_2_TEMPLATE_ID,
          step_type: 'step_2_appeal',
          field_values: makeStep2FieldValues(),
        }),
      }),
    })
    renderApp({
      initialEntries: [`/cases/${SAMPLE_CASE_UUID}/grievance`],
    })
    await user.click(
      await screen.findByRole('button', { name: 'Generate Grievance' }),
    )
    const draft = await screen.findByLabelText('Temporary grievance draft')
    expect(
      within(draft).getByText(new RegExp(OFFICIAL_STEP_2_TEMPLATE_ID)),
    ).toBeInTheDocument()
    expect(
      within(draft).getByText(/Official Standard Grievance Form — Step 2/i),
    ).toBeInTheDocument()
    expect(
      within(draft).getByLabelText(/USPS Number/i),
    ).toBeInTheDocument()
  })

  it('tracks steward overrides and keeps protected blanks blank', async () => {
    const user = userEvent.setup()
    const { saveCalls } = grievanceHandler({
      generateResponse: makeGenerateGrievanceResponse({
        grievance_generation: makeGrievanceGeneration({
          field_values: makeStep1FieldValues({
            form_date: '',
            ssn_or_employee_id: '',
          }),
        }),
      }),
    })
    renderApp({
      initialEntries: [`/cases/${SAMPLE_CASE_UUID}/grievance`],
    })
    await user.click(
      await screen.findByRole('button', { name: 'Generate Grievance' }),
    )
    const draft = await screen.findByLabelText('Temporary grievance draft')
    expect(within(draft).getByLabelText(/^Date\s*\*?$/i)).toHaveValue('')
    expect(within(draft).getByLabelText(/SSN or Employee ID/i)).toHaveValue('')
    expect(
      within(draft).getAllByText(/Protected field — leave blank/i).length,
    ).toBeGreaterThan(0)

    const facts = within(draft).getByLabelText(/Facts — What Happened/i)
    await user.clear(facts)
    await user.type(facts, 'Steward-revised facts.')
    expect(within(draft).getByText('Steward override')).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: 'Save' }))
    await waitFor(() => {
      expect(saveCalls).toHaveLength(1)
    })
    expect(saveCalls[0]?.steward_override_field_ids).toContain(
      'facts_what_happened',
    )
    expect(saveCalls[0]?.field_values?.ssn_or_employee_id).toBe('')
    expect(saveCalls[0]?.field_values?.form_date).toBe('')
  })

  it('required and protected validation summary works', async () => {
    const user = userEvent.setup()
    grievanceHandler({
      generateResponse: makeGenerateGrievanceResponse({
        grievance_generation: makeGrievanceGeneration({
          field_values: makeStep1FieldValues({
            form_date: '',
            branch_grievance_number: '',
            facts_what_happened: '',
          }),
        }),
      }),
    })
    renderApp({
      initialEntries: [`/cases/${SAMPLE_CASE_UUID}/grievance`],
    })
    await user.click(
      await screen.findByRole('button', { name: 'Generate Grievance' }),
    )
    await screen.findByLabelText('Temporary grievance draft')
    await user.click(screen.getByRole('button', { name: 'Validate' }))
    expect(
      await screen.findByText(/Missing required fields/i),
    ).toBeInTheDocument()
    expect(screen.getByText(/Protected fields left blank/i)).toBeInTheDocument()
    expect(
      document.activeElement?.id,
    ).toMatch(/^grievance-field-/)
  })

  it('Cancel clears draft, sends no Save, creates no saved artifact', async () => {
    const user = userEvent.setup()
    const { saveCalls, getArtifacts } = grievanceHandler()
    renderApp({
      initialEntries: [`/cases/${SAMPLE_CASE_UUID}/grievance`],
    })
    await user.click(
      await screen.findByRole('button', { name: 'Generate Grievance' }),
    )
    await screen.findByLabelText('Temporary grievance draft')
    await user.click(
      screen.getByRole('button', {
        name: 'Cancel temporary grievance draft',
      }),
    )
    await waitFor(() => {
      expect(
        screen.queryByLabelText('Temporary grievance draft'),
      ).not.toBeInTheDocument()
    })
    expect(saveCalls).toHaveLength(0)
    expect(getArtifacts()).toHaveLength(0)
    expect(
      screen.getByText(/No saved Step 1 or Step 2 grievance artifacts yet/i),
    ).toBeInTheDocument()
  })

  it('dirty Cancel asks for confirmation before discard', async () => {
    const user = userEvent.setup()
    grievanceHandler()
    renderApp({
      initialEntries: [`/cases/${SAMPLE_CASE_UUID}/grievance`],
    })
    await user.click(
      await screen.findByRole('button', { name: 'Generate Grievance' }),
    )
    const draft = await screen.findByLabelText('Temporary grievance draft')
    await user.type(
      within(draft).getByLabelText(/Branch Grievance Number/i),
      'BG-1',
    )
    await user.click(
      screen.getByRole('button', {
        name: 'Cancel temporary grievance draft',
      }),
    )
    expect(
      screen.getByRole('alertdialog', {
        name: /Discard unsaved grievance draft/i,
      }),
    ).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Keep draft' }))
    expect(
      screen.getByLabelText('Temporary grievance draft'),
    ).toBeInTheDocument()
    await user.click(
      screen.getByRole('button', {
        name: 'Cancel temporary grievance draft',
      }),
    )
    await user.click(screen.getByRole('button', { name: 'Discard draft' }))
    await waitFor(() => {
      expect(
        screen.queryByLabelText('Temporary grievance draft'),
      ).not.toBeInTheDocument()
    })
  })

  it('case switch clears temporary draft', async () => {
    const user = userEvent.setup()
    grievanceHandler()
    const { router } = renderApp({
      initialEntries: [`/cases/${SAMPLE_CASE_UUID}/grievance`],
    })
    await user.click(
      await screen.findByRole('button', { name: 'Generate Grievance' }),
    )
    expect(
      await screen.findByLabelText('Temporary grievance draft'),
    ).toBeInTheDocument()
    await router.navigate(`/cases/${OTHER_CASE_UUID}/grievance`)
    await waitFor(() => {
      expect(
        screen.queryByLabelText('Temporary grievance draft'),
      ).not.toBeInTheDocument()
    })
    expect(
      await screen.findByRole('button', { name: 'Generate Grievance' }),
    ).toBeInTheDocument()
    expect(
      screen.getByRole('heading', { level: 1, name: 'Other case' }),
    ).toBeInTheDocument()
  })

  it('Save and Save and Print use verified prepare_pdf payloads', async () => {
    const user = userEvent.setup()
    const { saveCalls } = grievanceHandler()
    renderApp({
      initialEntries: [`/cases/${SAMPLE_CASE_UUID}/grievance`],
    })
    await user.click(
      await screen.findByRole('button', { name: 'Generate Grievance' }),
    )
    await screen.findByLabelText('Temporary grievance draft')
    await user.click(screen.getByRole('button', { name: 'Save' }))
    await waitFor(() => expect(saveCalls).toHaveLength(1))
    expect(saveCalls[0]).toMatchObject({
      prepare_pdf: false,
      template_id: OFFICIAL_STEP_1_TEMPLATE_ID,
      idempotency_key: expect.any(String),
      steward_override_field_ids: expect.any(Array),
      missing_required_field_ids: expect.any(Array),
    })
    await waitFor(() => {
      expect(
        screen.queryByLabelText('Temporary grievance draft'),
      ).not.toBeInTheDocument()
    })
    expect(
      await screen.findByRole('button', {
        name: /Official Grievance Worksheet — Step 1/i,
      }),
    ).toBeInTheDocument()

    await user.click(
      screen.getByRole('button', { name: 'Generate Grievance' }),
    )
    await screen.findByLabelText('Temporary grievance draft')
    await user.click(screen.getByRole('button', { name: 'Save and Print' }))
    await waitFor(() => expect(saveCalls).toHaveLength(2))
    expect(saveCalls[1]).toMatchObject({
      prepare_pdf: true,
      template_id: OFFICIAL_STEP_1_TEMPLATE_ID,
    })
    expect(saveCalls[0]?.idempotency_key).not.toEqual(
      saveCalls[1]?.idempotency_key,
    )
  })

  it('keeps idempotency key stable during save retry', async () => {
    const user = userEvent.setup()
    let attempts = 0
    const { saveCalls } = grievanceHandler({
      onSave: () => {
        attempts += 1
        if (attempts === 1) {
          return jsonResponse({ detail: 'Temporary failure' }, 500)
        }
        return jsonResponse(makeGrievanceSaveResponse())
      },
    })
    renderApp({
      initialEntries: [`/cases/${SAMPLE_CASE_UUID}/grievance`],
    })
    await user.click(
      await screen.findByRole('button', { name: 'Generate Grievance' }),
    )
    await user.click(await screen.findByRole('button', { name: 'Save' }))
    expect(await screen.findByRole('alert')).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Retry save' }))
    await waitFor(() => expect(saveCalls).toHaveLength(2))
    expect(saveCalls[0]?.idempotency_key).toBe(saveCalls[1]?.idempotency_key)
  })

  it('presents saved_pdf_failed as saved-with-warning', async () => {
    const user = userEvent.setup()
    grievanceHandler({
      onSave: () =>
        jsonResponse(
          makeGrievanceSaveResponse({
            status: 'saved_pdf_failed',
            message: 'Official grievance saved; PDF preparation failed.',
            print_ready: false,
            pdf_error: 'acroform failed',
            artifact: makeGrievanceArtifactSummary({
              pdf_status: 'failed',
            }),
          }),
        ),
    })
    renderApp({
      initialEntries: [`/cases/${SAMPLE_CASE_UUID}/grievance`],
    })
    await user.click(
      await screen.findByRole('button', { name: 'Generate Grievance' }),
    )
    await user.click(
      await screen.findByRole('button', { name: 'Save and Print' }),
    )
    expect(
      await screen.findByText(
        /Grievance saved successfully, but PDF preparation failed/i,
      ),
    ).toBeInTheDocument()
  })

  it('presents idempotent replay without duplicating artifacts', async () => {
    const user = userEvent.setup()
    grievanceHandler({
      artifacts: [makeGrievanceArtifactSummary()],
      onSave: () =>
        jsonResponse(
          makeGrievanceSaveResponse({
            status: 'idempotent_replay',
            message: 'Idempotent Save and Print replay; no new artifact.',
          }),
        ),
    })
    renderApp({
      initialEntries: [`/cases/${SAMPLE_CASE_UUID}/grievance`],
    })
    await user.click(
      await screen.findByRole('button', { name: 'Generate Grievance' }),
    )
    await user.click(await screen.findByRole('button', { name: 'Save' }))
    expect(
      await screen.findByText(/no duplicate grievance artifact/i),
    ).toBeInTheDocument()
  })

  it('labels Step 1 official PDF and revokes blob URLs', async () => {
    const user = userEvent.setup()
    const revokeSpy = vi.spyOn(URL, 'revokeObjectURL')
    const createSpy = vi
      .spyOn(URL, 'createObjectURL')
      .mockReturnValue('blob:test-grievance-step1')

    grievanceHandler({
      artifacts: [
        makeGrievanceArtifactSummary({
          artifact_uuid: SAMPLE_GRIEVANCE_ARTIFACT_UUID,
          template_id: OFFICIAL_STEP_1_TEMPLATE_ID,
          pdf_status: 'ready',
        }),
      ],
    })
    const view = renderApp({
      initialEntries: [
        `/cases/${SAMPLE_CASE_UUID}/grievance?artifact=${SAMPLE_GRIEVANCE_ARTIFACT_UUID}`,
      ],
    })
    await user.click(
      await screen.findByRole('button', {
        name: /Preview Official Step 1 grievance worksheet PDF/i,
      }),
    )
    expect(
      await screen.findByTitle('Official Step 1 grievance worksheet PDF'),
    ).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Close preview' }))
    expect(revokeSpy).toHaveBeenCalled()
    view.unmount()
    createSpy.mockRestore()
    revokeSpy.mockRestore()
  })

  it('labels Step 2 official PDF correctly', async () => {
    const user = userEvent.setup()
    const createSpy = vi
      .spyOn(URL, 'createObjectURL')
      .mockReturnValue('blob:test-grievance-step2')

    grievanceHandler({
      artifacts: [
        makeGrievanceArtifactSummary({
          artifact_uuid: SAMPLE_GRIEVANCE_ARTIFACT_UUID,
          template_id: OFFICIAL_STEP_2_TEMPLATE_ID,
          grievance_step: 'step_2_appeal',
          title: 'Official Standard Grievance Form — Step 2 v1',
          pdf_status: 'ready',
        }),
      ],
    })
    renderApp({
      initialEntries: [
        `/cases/${SAMPLE_CASE_UUID}/grievance?artifact=${SAMPLE_GRIEVANCE_ARTIFACT_UUID}`,
      ],
    })
    await user.click(
      await screen.findByRole('button', {
        name: /Preview Official Step 2 standard grievance form PDF/i,
      }),
    )
    expect(
      await screen.findByTitle('Official Step 2 standard grievance form PDF'),
    ).toBeInTheDocument()
    createSpy.mockRestore()
  })

  it('maps PDF 409/unavailable to steward-language errors', async () => {
    const user = userEvent.setup()
    grievanceHandler({
      artifacts: [makeGrievanceArtifactSummary({ pdf_status: 'ready' })],
      pdfStatus: 409,
    })
    renderApp({
      initialEntries: [
        `/cases/${SAMPLE_CASE_UUID}/grievance?artifact=${SAMPLE_GRIEVANCE_ARTIFACT_UUID}`,
      ],
    })
    await user.click(
      await screen.findByRole('button', {
        name: /Preview Official Step 1 grievance worksheet PDF/i,
      }),
    )
    expect(await screen.findByRole('alert')).toHaveTextContent(
      /not ready yet/i,
    )
  })

  it('refresh restores saved grievances; temporary draft does not restore', async () => {
    const user = userEvent.setup()
    grievanceHandler({
      artifacts: [makeGrievanceArtifactSummary()],
    })
    const first = renderApp({
      initialEntries: [`/cases/${SAMPLE_CASE_UUID}/grievance`],
    })
    expect(
      await screen.findByRole('button', {
        name: /Official Grievance Worksheet — Step 1/i,
      }),
    ).toBeInTheDocument()
    await user.click(
      screen.getByRole('button', { name: 'Generate Grievance' }),
    )
    expect(
      await screen.findByLabelText('Temporary grievance draft'),
    ).toBeInTheDocument()
    first.unmount()

    grievanceHandler({
      artifacts: [makeGrievanceArtifactSummary()],
    })
    renderApp({
      initialEntries: [`/cases/${SAMPLE_CASE_UUID}/grievance`],
    })
    expect(
      await screen.findByRole('button', {
        name: /Official Grievance Worksheet — Step 1/i,
      }),
    ).toBeInTheDocument()
    expect(
      screen.queryByLabelText('Temporary grievance draft'),
    ).not.toBeInTheDocument()
  })

  it('conversation, analysis, and evidence do not generate grievances', async () => {
    const { generateCalls, fetchMock } = grievanceHandler({
      artifacts: [],
    })
    renderApp({
      initialEntries: [`/cases/${SAMPLE_CASE_UUID}/conversation`],
    })
    await screen.findByRole('heading', { name: 'Conversation' })
    expect(generateCalls).toHaveLength(0)

    const analysis = renderApp({
      initialEntries: [`/cases/${SAMPLE_CASE_UUID}/analysis`],
    })
    await screen.findByRole('heading', { name: 'Analysis' })
    expect(
      screen.queryByRole('button', { name: /Generate Grievance/i }),
    ).not.toBeInTheDocument()
    expect(generateCalls).toHaveLength(0)
    analysis.unmount()

    const evidence = renderApp({
      initialEntries: [`/cases/${SAMPLE_CASE_UUID}/evidence`],
    })
    await screen.findByRole('heading', { name: 'Evidence' })
    expect(generateCalls).toHaveLength(0)
    const urls = fetchMock.mock.calls.map((call) => String(call[0]))
    expect(urls.some((url) => /\/grievances\/save-and-print/.test(url))).toBe(
      false,
    )
    evidence.unmount()
  })

  it('does not call artifact compare or source administration endpoints', async () => {
    const { artifactCompareCalls, sourcesCalls } = grievanceHandler({
      artifacts: [makeGrievanceArtifactSummary()],
    })
    renderApp({
      initialEntries: [`/cases/${SAMPLE_CASE_UUID}/grievance`],
    })
    await screen.findByRole('heading', { name: 'Grievance' })
    expect(artifactCompareCalls).toHaveLength(0)
    expect(sourcesCalls).toHaveLength(0)
    expect(screen.queryByText(/Artifact Library/i)).not.toBeInTheDocument()
    expect(screen.queryByText(/Compare artifacts/i)).not.toBeInTheDocument()
    expect(
      screen.queryByRole('button', { name: /Step 3/i }),
    ).not.toBeInTheDocument()
  })
})
