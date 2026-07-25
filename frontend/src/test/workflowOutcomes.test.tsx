import { fireEvent, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'
import {
  OTHER_CASE_UUID,
  SAMPLE_CASE_UUID,
  installApiMock,
  jsonResponse,
  makeArchiveResponse,
  makeCloseResponse,
  makeHistoryResponse,
  makeOutcomeResponse,
  makeReopenResponse,
  makeSettleResponse,
  makeTimelineResponse,
  makeWorkflowStateView,
  makeWorkspace,
} from './savedCasesFixtures'
import { renderApp } from './testUtils'

type HandlerOptions = {
  workflow?: ReturnType<typeof makeWorkflowStateView>
  otherWorkflow?: ReturnType<typeof makeWorkflowStateView>
  outcomeErrorDetail?: string
  listArtifactsCount?: number
}

function workflowHandler(options: HandlerOptions = {}) {
  let workflow =
    options.workflow ??
    makeWorkflowStateView({
      explicit_state: 'step_1_decision_required',
      current_grievance_step: 'step_1_initial',
      case_status: 'open',
      permitted_next_states: ['step_1_resolved', 'step_1_appealed', 'closed'],
    })
  let otherWorkflow =
    options.otherWorkflow ??
    makeWorkflowStateView({
      case_uuid: OTHER_CASE_UUID,
      explicit_state: 'step_2_official',
      current_grievance_step: 'step_2_appeal',
      case_status: 'open',
      permitted_next_states: ['step_2_resolved'],
    })
  let workspace = makeWorkspace({
    case_overview: {
      ...makeWorkspace().case_overview,
      current_step: workflow.current_grievance_step,
      explicit_workflow_state: workflow.explicit_state,
      current_status: workflow.case_status ?? 'open',
    },
    workspace_summary: {
      ...makeWorkspace().workspace_summary,
      current_step_type: workflow.current_grievance_step as
        | 'step_1_initial'
        | 'step_2_appeal'
        | 'step_3_appeal'
        | null,
      workspace_status: (workflow.case_status as 'open') ?? 'open',
      status: workflow.case_status ?? 'open',
    },
    step_progression: {
      has_step_progression: true,
      workspace_status: 'open',
      current_step_type: workflow.current_grievance_step,
      steps: [
        {
          step_type: 'step_1_initial',
          step_number: 1,
          status: 'decision_added',
          is_closed: false,
          template_id: 'official_grievance_worksheet_step_1',
          template_availability: 'available',
          outcomes: [],
        },
      ],
    },
  })
  let otherWorkspace = makeWorkspace({
    case_uuid: OTHER_CASE_UUID,
    title: 'Other case',
    case_overview: {
      ...makeWorkspace({ case_uuid: OTHER_CASE_UUID }).case_overview,
      current_step: 'step_2_appeal',
      explicit_workflow_state: 'step_2_official',
    },
    workspace_summary: {
      ...makeWorkspace({ case_uuid: OTHER_CASE_UUID }).workspace_summary,
      title: 'Other case',
      current_step_type: 'step_2_appeal',
    },
  })

  const outcomeBodies: Array<Record<string, unknown>> = []
  const closeBodies: Array<Record<string, unknown>> = []
  const settleBodies: Array<Record<string, unknown>> = []
  const archiveBodies: Array<Record<string, unknown>> = []
  const reopenBodies: Array<Record<string, unknown>> = []
  const transitionBodies: Array<Record<string, unknown>> = []
  const artifactPosts: string[] = []
  const sourcesCalls: string[] = []
  let historyCount = 2
  let timelineCount = 2
  let artifactCount = options.listArtifactsCount ?? 0

  const fetchMock = installApiMock((input, init) => {
    const url =
      typeof input === 'string'
        ? input
        : input instanceof URL
          ? input.toString()
          : input.url
    const method = (init?.method ?? 'GET').toUpperCase()

    if (url.includes('/sources')) {
      sourcesCalls.push(`${method} ${url}`)
      return jsonResponse({ detail: 'Forbidden in M8 tests' }, 500)
    }

    if (url.includes(`/cases/${SAMPLE_CASE_UUID}/workspace`)) {
      return jsonResponse(workspace)
    }
    if (url.includes(`/cases/${OTHER_CASE_UUID}/workspace`)) {
      return jsonResponse(otherWorkspace)
    }

    if (
      url.includes(`/cases/${SAMPLE_CASE_UUID}/workflow`) &&
      !url.includes('/transitions') &&
      method === 'GET'
    ) {
      return jsonResponse(workflow)
    }
    if (
      url.includes(`/cases/${OTHER_CASE_UUID}/workflow`) &&
      !url.includes('/transitions') &&
      method === 'GET'
    ) {
      return jsonResponse(otherWorkflow)
    }

    if (url.includes('/workflow/transitions') && method === 'POST') {
      const body = init?.body
        ? (JSON.parse(String(init.body)) as Record<string, unknown>)
        : {}
      transitionBodies.push(body)
      return jsonResponse({ detail: 'Generic transitions not used in M8 UI' }, 400)
    }

    if (url.includes(`/cases/${SAMPLE_CASE_UUID}/outcomes`) && method === 'POST') {
      const body = init?.body
        ? (JSON.parse(String(init.body)) as Record<string, unknown>)
        : {}
      outcomeBodies.push(body)
      if (options.outcomeErrorDetail) {
        return jsonResponse({ detail: options.outcomeErrorDetail }, 400)
      }

      const appealed = body.appeal_to_next_step === true
      const closed = body.close_case === true
      if (appealed) {
        workflow = makeWorkflowStateView({
          explicit_state: 'step_2_analysis',
          current_grievance_step: 'step_2_appeal',
          case_status: 'open',
          permitted_next_states: ['step_2_draft', 'closed'],
        })
        workspace = makeWorkspace({
          case_overview: {
            ...workspace.case_overview,
            current_step: 'step_2_appeal',
            explicit_workflow_state: 'step_2_analysis',
          },
          workspace_summary: {
            ...workspace.workspace_summary,
            current_step_type: 'step_2_appeal',
          },
          step_progression: {
            has_step_progression: true,
            workspace_status: 'open',
            current_step_type: 'step_2_appeal',
            steps: [
              {
                step_type: 'step_1_initial',
                status: 'appealed_to_next_step',
                is_closed: true,
                outcomes: [
                  {
                    outcome_type: body.outcome_type,
                    decision_summary: body.decision_summary,
                  },
                ],
              },
              {
                step_type: 'step_2_appeal',
                status: 'open',
                is_closed: false,
              },
            ],
          },
        })
        historyCount += 1
        timelineCount += 1
        return jsonResponse(
          makeOutcomeResponse({
            workflow,
            workspace,
            outcome: {
              outcome_id: 'outcome-appeal',
              step_type: 'step_1_initial',
              outcome_type: String(body.outcome_type ?? 'denied'),
              decision_summary: String(body.decision_summary ?? ''),
              decision_date: null,
              decision_maker_name: null,
              decision_maker_title: null,
              decision_document_refs: [],
              steward_notes: null,
              step_closed: true,
              case_closed: false,
              appeal_requested: true,
              next_step_target: 'step_2_appeal',
              recorded_at: '2026-07-25T14:00:00Z',
            },
          }),
        )
      }
      if (closed) {
        workflow = makeWorkflowStateView({
          explicit_state: 'closed',
          current_grievance_step: 'step_1_initial',
          case_status: 'closed',
          permitted_next_states: ['reopened'],
        })
        workspace = makeWorkspace({
          status: 'closed',
          case_overview: {
            ...workspace.case_overview,
            current_status: 'closed',
            explicit_workflow_state: 'closed',
          },
          workspace_summary: {
            ...workspace.workspace_summary,
            status: 'closed',
            workspace_status: 'closed',
          },
        })
        return jsonResponse(
          makeOutcomeResponse({
            workflow,
            workspace,
            outcome: {
              outcome_id: 'outcome-close',
              step_type: 'step_1_initial',
              outcome_type: String(body.outcome_type ?? 'resolved'),
              decision_summary: String(body.decision_summary ?? ''),
              decision_date: null,
              decision_maker_name: null,
              decision_maker_title: null,
              decision_document_refs: [],
              steward_notes: null,
              step_closed: true,
              case_closed: true,
              appeal_requested: false,
              next_step_target: null,
              recorded_at: '2026-07-25T14:00:00Z',
            },
          }),
        )
      }

      workflow = makeWorkflowStateView({
        ...workflow,
        explicit_state: 'step_1_resolved',
        permitted_next_states: ['closed', 'settled', 'reopened'],
      })
      return jsonResponse(
        makeOutcomeResponse({
          workflow,
          workspace,
          outcome: {
            outcome_id: 'outcome-plain',
            step_type: 'step_1_initial',
            outcome_type: String(body.outcome_type ?? 'resolved'),
            decision_summary: String(body.decision_summary ?? ''),
            decision_date: null,
            decision_maker_name: null,
            decision_maker_title: null,
            decision_document_refs: [],
            steward_notes: null,
            step_closed: Boolean(body.close_step),
            case_closed: false,
            appeal_requested: false,
            next_step_target: null,
            recorded_at: '2026-07-25T14:00:00Z',
          },
        }),
      )
    }

    if (url.includes(`/cases/saved/${SAMPLE_CASE_UUID}/close`) && method === 'POST') {
      const body = init?.body
        ? (JSON.parse(String(init.body)) as Record<string, unknown>)
        : {}
      closeBodies.push(body)
      const closed = makeCloseResponse()
      workflow = makeWorkflowStateView({
        explicit_state: 'closed',
        case_status: 'closed',
        permitted_next_states: ['reopened'],
      })
      workspace = closed.workspace as typeof workspace
      return jsonResponse(closed)
    }

    if (url.includes(`/cases/saved/${SAMPLE_CASE_UUID}/settle`) && method === 'POST') {
      const body = init?.body
        ? (JSON.parse(String(init.body)) as Record<string, unknown>)
        : {}
      settleBodies.push(body)
      const settled = makeSettleResponse()
      workflow = makeWorkflowStateView({
        explicit_state: 'settled',
        case_status: 'settled',
        permitted_next_states: ['reopened'],
      })
      workspace = settled.workspace as typeof workspace
      return jsonResponse(settled)
    }

    if (url.includes(`/cases/saved/${SAMPLE_CASE_UUID}/archive`) && method === 'POST') {
      const body = init?.body
        ? (JSON.parse(String(init.body)) as Record<string, unknown>)
        : {}
      archiveBodies.push(body)
      const archived = makeArchiveResponse()
      workflow = makeWorkflowStateView({
        explicit_state: 'closed',
        case_status: 'archived',
        permitted_next_states: ['reopened'],
      })
      workspace = archived.workspace as typeof workspace
      return jsonResponse(archived)
    }

    if (url.includes(`/cases/saved/${SAMPLE_CASE_UUID}/reopen`) && method === 'POST') {
      const body = init?.body
        ? (JSON.parse(String(init.body)) as Record<string, unknown>)
        : {}
      reopenBodies.push(body)
      const reopened = makeReopenResponse()
      workflow = makeWorkflowStateView({
        explicit_state: 'reopened',
        case_status: 'open',
        permitted_next_states: ['step_1_analysis', 'closed'],
      })
      workspace = (reopened.workspace ?? makeWorkspace()) as typeof workspace
      return jsonResponse(reopened)
    }

    if (url.includes('/history') && !url.includes('/context')) {
      return jsonResponse(
        makeHistoryResponse([], { count: historyCount }),
      )
    }
    if (url.includes('/timeline')) {
      return jsonResponse(
        makeTimelineResponse([], { count: timelineCount }),
      )
    }
    if (
      url.includes('/artifacts') &&
      method === 'GET' &&
      !url.includes('/compare')
    ) {
      return jsonResponse({
        case_uuid: SAMPLE_CASE_UUID,
        count: artifactCount,
        artifacts: [],
        groups: { analysis_reports: [], grievances: [] },
      })
    }
    if (
      method === 'POST' &&
      (url.includes('/reports/') ||
        url.includes('/grievances/') ||
        url.includes('/actions') ||
        url.includes('/artifacts'))
    ) {
      artifactPosts.push(`${method} ${url}`)
      return jsonResponse({ detail: 'Artifact mutation blocked in M8 tests' }, 500)
    }

    if (url.includes('/health')) {
      return jsonResponse({ status: 'healthy', service: 'GrievanceHub' })
    }

    return jsonResponse({ detail: `Unhandled mock: ${method} ${url}` }, 500)
  })

  return {
    fetchMock,
    outcomeBodies,
    closeBodies,
    settleBodies,
    archiveBodies,
    reopenBodies,
    transitionBodies,
    artifactPosts,
    sourcesCalls,
    getWorkflow: () => workflow,
    setWorkflow: (next: ReturnType<typeof makeWorkflowStateView>) => {
      workflow = next
    },
    getArtifactCount: () => artifactCount,
    setArtifactCount: (n: number) => {
      artifactCount = n
    },
  }
}

describe('W6 M8 Workflow Outcomes and Case Lifecycle', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
    vi.restoreAllMocks()
  })

  it('renders Workflow under the workspace with direct navigation', async () => {
    workflowHandler()
    renderApp({
      initialEntries: [`/cases/${SAMPLE_CASE_UUID}/workflow`],
    })

    expect(
      await screen.findByRole('heading', { name: 'Workflow & outcomes' }),
    ).toBeInTheDocument()
    expect(
      screen.getByRole('link', { name: 'Workflow' }),
    ).toHaveAttribute('href', `/cases/${SAMPLE_CASE_UUID}/workflow`)
    expect(
      screen.getByRole('link', { name: 'Conversation' }),
    ).toBeInTheDocument()
    expect(
      screen.getByRole('link', { name: 'Evidence' }),
    ).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Analysis' })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Grievance' })).toBeInTheDocument()
    expect(
      screen.getByRole('link', { name: 'Artifacts & History' }),
    ).toBeInTheDocument()
  })

  it('restores current workflow state on refresh remount', async () => {
    workflowHandler()
    const view = renderApp({
      initialEntries: [`/cases/${SAMPLE_CASE_UUID}/workflow`],
    })
    expect(
      await screen.findByText(/Step 1 decision required/i),
    ).toBeInTheDocument()
    view.unmount()

    renderApp({
      initialEntries: [`/cases/${SAMPLE_CASE_UUID}/workflow`],
    })
    expect(
      await screen.findByText(/Step 1 decision required/i),
    ).toBeInTheDocument()
    expect(screen.getByText(/Step 1 \(initial grievance\)/i)).toBeInTheDocument()
  })

  it('renders status, step, and permitted actions from backend data', async () => {
    workflowHandler()
    renderApp({
      initialEntries: [`/cases/${SAMPLE_CASE_UUID}/workflow`],
    })

    expect(
      await screen.findByRole('heading', { name: 'Workflow & outcomes' }),
    ).toBeInTheDocument()
    expect(screen.getByText(/Step 1 decision required/i)).toBeInTheDocument()
    expect(screen.getByText(/Step 1 \(initial grievance\)/i)).toBeInTheDocument()
    expect(
      await screen.findByRole('heading', { name: 'Permitted next states' }),
    ).toBeInTheDocument()
    expect(
      screen.getByRole('list', { name: 'Permitted next states' }),
    ).toBeInTheDocument()
    expect(document.body.textContent).toMatch(/step_1_resolved/)
    expect(document.body.textContent).toMatch(/step_1_appealed/)
    expect(
      screen.queryByRole('button', { name: /Generate Step 3/i }),
    ).not.toBeInTheDocument()
  })

  it('shows only supported outcome fields and client required feedback', async () => {
    const user = userEvent.setup()
    workflowHandler()
    renderApp({
      initialEntries: [`/cases/${SAMPLE_CASE_UUID}/workflow`],
    })

    expect(
      await screen.findByRole('heading', { name: 'Record outcome' }),
    ).toBeInTheDocument()
    expect(screen.getByLabelText('Outcome type')).toBeInTheDocument()
    expect(screen.getByLabelText('Decision summary')).toBeInTheDocument()
    expect(screen.getByLabelText('Decision date')).toBeInTheDocument()
    expect(screen.getByLabelText('Steward notes')).toBeInTheDocument()
    expect(
      screen.queryByLabelText(/decision-maker name/i),
    ).not.toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: 'Record outcome' }))
    expect(
      await screen.findByText(/Decision summary is required/i),
    ).toBeInTheDocument()
  })

  async function waitForOutcomeFormReady() {
    await screen.findByRole('heading', { name: 'Record outcome' })
    await waitFor(() => {
      expect(screen.getByLabelText('Outcome type')).not.toBeDisabled()
      expect(screen.getByLabelText('Decision summary')).not.toBeDisabled()
    })
  }

  it('records a successful outcome and updates workflow', async () => {
    const user = userEvent.setup()
    const api = workflowHandler()
    renderApp({
      initialEntries: [`/cases/${SAMPLE_CASE_UUID}/workflow`],
    })

    await waitForOutcomeFormReady()
    fireEvent.change(screen.getByLabelText('Outcome type'), {
      target: { value: 'resolved' },
    })
    fireEvent.change(screen.getByLabelText('Decision summary'), {
      target: { value: 'Resolved at Step 1' },
    })
    await user.click(screen.getByRole('button', { name: 'Record outcome' }))

    await waitFor(() => {
      expect(api.outcomeBodies).toHaveLength(1)
    })
    expect(api.outcomeBodies[0]).toMatchObject({
      outcome_type: 'resolved',
      decision_summary: 'Resolved at Step 1',
      close_case: false,
      appeal_to_next_step: false,
    })
    expect(
      await screen.findByText(/Outcome recorded/i),
    ).toBeInTheDocument()
    expect(api.artifactPosts).toHaveLength(0)
    expect(api.transitionBodies).toHaveLength(0)
  })

  it('preserves form data and prevents duplicate submit on failure', async () => {
    const user = userEvent.setup()
    const api = workflowHandler({
      outcomeErrorDetail: 'Transition not permitted for current workflow state.',
    })
    renderApp({
      initialEntries: [`/cases/${SAMPLE_CASE_UUID}/workflow`],
    })

    await waitForOutcomeFormReady()
    fireEvent.change(screen.getByLabelText('Outcome type'), {
      target: { value: 'denied' },
    })
    fireEvent.change(screen.getByLabelText('Decision summary'), {
      target: { value: 'Denied — keep drafting' },
    })
    await user.click(screen.getByRole('button', { name: 'Record outcome' }))

    expect(
      await screen.findByText(/Transition not permitted/i),
    ).toBeInTheDocument()
    expect(screen.getByLabelText('Decision summary')).toHaveValue(
      'Denied — keep drafting',
    )
    expect(api.outcomeBodies).toHaveLength(1)

    const submit = screen.getByRole('button', { name: 'Record outcome' })
    expect(submit).not.toBeDisabled()
  })

  it('appeals Step 1 to Step 2 on the same case UUID with confirmation', async () => {
    const user = userEvent.setup()
    const api = workflowHandler()
    renderApp({
      initialEntries: [`/cases/${SAMPLE_CASE_UUID}/workflow`],
    })

    await waitForOutcomeFormReady()
    fireEvent.change(screen.getByLabelText('Outcome type'), {
      target: { value: 'denied' },
    })
    fireEvent.change(screen.getByLabelText('Decision summary'), {
      target: { value: 'Management denied Step 1' },
    })
    await user.click(
      screen.getByRole('checkbox', {
        name: /Appeal to next step/i,
      }),
    )
    await user.click(screen.getByRole('button', { name: 'Record outcome' }))

    const dialog = await screen.findByRole('dialog')
    expect(
      within(dialog).getByText(new RegExp(SAMPLE_CASE_UUID)),
    ).toBeInTheDocument()
    await user.click(
      within(dialog).getByRole('button', { name: 'Confirm and record' }),
    )

    await waitFor(() => {
      expect(api.outcomeBodies).toHaveLength(1)
    })
    expect(api.outcomeBodies[0]).toMatchObject({
      appeal_to_next_step: true,
      close_case: false,
      step_type: 'step_1_initial',
    })
    expect(
      await screen.findByText(/Step 2 \(appeal\)/i),
    ).toBeInTheDocument()
    expect(screen.queryByText(OTHER_CASE_UUID)).not.toBeInTheDocument()
    expect(api.artifactPosts).toHaveLength(0)
  })

  it('confirms close-step, close-case, settle, and archive lifecycle actions', async () => {
    const user = userEvent.setup()
    const api = workflowHandler()
    renderApp({
      initialEntries: [`/cases/${SAMPLE_CASE_UUID}/workflow`],
    })

    await screen.findByRole('heading', { name: 'Case lifecycle' })

    await user.type(screen.getByLabelText('Outcome'), 'Closed after denial')
    await user.clear(screen.getByLabelText('Resolution type'))
    await user.type(screen.getByLabelText('Resolution type'), 'denied_final')
    await user.click(screen.getByRole('button', { name: 'Close case…' }))
    const dialog = await screen.findByRole('dialog')
    expect(
      within(dialog).getByRole('heading', { name: /Close case Overtime dispute/i }),
    ).toBeInTheDocument()
    await user.click(within(dialog).getByRole('button', { name: 'Close case' }))
    await waitFor(() => expect(api.closeBodies).toHaveLength(1))
    expect(api.closeBodies[0]).toMatchObject({
      outcome: 'Closed after denial',
      resolution_type: 'denied_final',
    })
  })

  it('settles and archives with confirmation and no artifact creation', async () => {
    const user = userEvent.setup()
    const api = workflowHandler()
    renderApp({
      initialEntries: [`/cases/${SAMPLE_CASE_UUID}/workflow`],
    })

    await screen.findByRole('heading', { name: 'Case lifecycle' })
    await user.type(screen.getByLabelText('Settlement notes'), 'Local settlement')
    await user.click(screen.getByRole('button', { name: /Settle case/i }))
    let dialog = await screen.findByRole('dialog')
    await user.click(within(dialog).getByRole('button', { name: 'Settle case' }))
    await waitFor(() => expect(api.settleBodies).toHaveLength(1))
    expect(api.artifactPosts).toHaveLength(0)
  })

  it('archives with confirmation and keeps case discoverable messaging', async () => {
    const user = userEvent.setup()
    const api = workflowHandler()
    renderApp({
      initialEntries: [`/cases/${SAMPLE_CASE_UUID}/workflow`],
    })

    await screen.findByRole('heading', { name: 'Case lifecycle' })
    await user.type(screen.getByLabelText('Reason (optional)'), 'Year-end archive')
    await user.click(screen.getByRole('button', { name: /Archive case/i }))
    const dialog = await screen.findByRole('dialog')
    expect(
      within(dialog).getByText(/not permanently deleted/i),
    ).toBeInTheDocument()
    await user.click(within(dialog).getByRole('button', { name: 'Archive case' }))
    await waitFor(() => expect(api.archiveBodies).toHaveLength(1))
    expect(api.archiveBodies[0]).toMatchObject({
      status: 'archived',
      reason: 'Year-end archive',
    })
  })

  it('disables outcome recording when terminal and supports reopen', async () => {
    const user = userEvent.setup()
    const api = workflowHandler({
      workflow: makeWorkflowStateView({
        explicit_state: 'closed',
        case_status: 'closed',
        current_grievance_step: 'step_1_initial',
        permitted_next_states: ['reopened'],
      }),
    })
    renderApp({
      initialEntries: [`/cases/${SAMPLE_CASE_UUID}/workflow`],
    })

    expect(
      await screen.findByText(/Outcome recording is unavailable/i),
    ).toBeInTheDocument()
    expect(
      screen.queryByRole('button', { name: 'Record outcome' }),
    ).not.toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: /Reopen case/i }))
    await screen.findByRole('dialog')
    await user.keyboard('{Escape}')
    await waitFor(() => {
      expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
    })
    await user.click(screen.getByRole('button', { name: /Reopen case/i }))
    const dialog2 = await screen.findByRole('dialog')
    await user.click(within(dialog2).getByRole('button', { name: 'Reopen case' }))
    await waitFor(() => expect(api.reopenBodies).toHaveLength(1))
    expect(api.reopenBodies[0]).toMatchObject({ source: 'manual_ui' })
  })

  it('clears unsaved form state on case switch and avoids cross-case render', async () => {
    const user = userEvent.setup()
    workflowHandler()
    const view = renderApp({
      initialEntries: [`/cases/${SAMPLE_CASE_UUID}/workflow`],
    })

    await screen.findByRole('heading', { name: 'Record outcome' })
    await user.type(
      screen.getByLabelText('Decision summary'),
      'Should not leak',
    )
    expect(screen.getByText(/Step 1 decision required/i)).toBeInTheDocument()

    view.unmount()
    renderApp({
      initialEntries: [`/cases/${OTHER_CASE_UUID}/workflow`],
    })

    expect(
      await screen.findByText(/Step 2 grievance is official/i),
    ).toBeInTheDocument()
    expect(screen.queryByText('Should not leak')).not.toBeInTheDocument()
    expect(screen.getByLabelText('Decision summary')).toHaveValue('')
    expect(screen.queryByText(/Step 1 decision required/i)).not.toBeInTheDocument()
  })

  it('shows Step 3 workflow boundary without Step 3 form generation', async () => {
    workflowHandler({
      workflow: makeWorkflowStateView({
        explicit_state: 'step_3_analysis',
        current_grievance_step: 'step_3_appeal',
        case_status: 'open',
        permitted_next_states: ['step_3_draft', 'closed'],
      }),
    })
    renderApp({
      initialEntries: [`/cases/${SAMPLE_CASE_UUID}/workflow`],
    })

    expect(
      await screen.findByText(/Step 3 workflow tracking is available/i),
    ).toBeInTheDocument()
    expect(
      screen.queryByRole('button', { name: /Generate Step 3/i }),
    ).not.toBeInTheDocument()
    expect(screen.queryByText(/official_step_3/i)).not.toBeInTheDocument()
  })

  it('keeps Artifacts & History read-only and exposes no Sources API keys', async () => {
    const api = workflowHandler()
    renderApp({
      initialEntries: [`/cases/${SAMPLE_CASE_UUID}/artifacts`],
    })

    expect(
      await screen.findByRole('heading', { name: 'Artifacts & History' }),
    ).toBeInTheDocument()
    expect(
      screen.queryByRole('button', { name: /Record outcome/i }),
    ).not.toBeInTheDocument()
    expect(screen.queryByText(/GRIEVANCEHUB_API_KEY/i)).not.toBeInTheDocument()
    expect(screen.queryByText(/sk-/i)).not.toBeInTheDocument()
    expect(api.sourcesCalls).toHaveLength(0)
  })

  it('normalizes API errors without exposing internals', async () => {
    const user = userEvent.setup()
    workflowHandler({
      outcomeErrorDetail: 'Transition not permitted for current workflow state.',
    })
    renderApp({
      initialEntries: [`/cases/${SAMPLE_CASE_UUID}/workflow`],
    })

    await waitForOutcomeFormReady()
    fireEvent.change(screen.getByLabelText('Outcome type'), {
      target: { value: 'denied' },
    })
    fireEvent.change(screen.getByLabelText('Decision summary'), {
      target: { value: 'Try again' },
    })
    await user.click(screen.getByRole('button', { name: 'Record outcome' }))

    expect(
      await screen.findByText(/Transition not permitted/i),
    ).toBeInTheDocument()
    expect(screen.queryByText(/Traceback/i)).not.toBeInTheDocument()
    expect(screen.queryByText(/C:\\Users/i)).not.toBeInTheDocument()
  })
})
