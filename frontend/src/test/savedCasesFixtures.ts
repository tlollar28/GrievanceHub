import { vi } from 'vitest'
import type {
  OpenCaseResponse,
  ReopenCaseResponse,
  SavedCaseListResponse,
  SavedCaseSummary,
} from '../api/types/savedCases'
import type { CaseWorkspace } from '../api/types/workspace'
import type {
  CaseDetail,
  CreateCaseResponse,
  UpdateFactsResponse,
} from '../api/types/cases'

export const SAMPLE_CASE_UUID = '11111111-1111-4111-8111-111111111111'
export const CLOSED_CASE_UUID = '22222222-2222-4222-8222-222222222222'
export const OTHER_CASE_UUID = '33333333-3333-4333-8333-333333333333'

export function makeSummary(
  overrides: Partial<SavedCaseSummary> = {},
): SavedCaseSummary {
  return {
    case_id: 501,
    case_uuid: SAMPLE_CASE_UUID,
    case_number: '501',
    title: 'Overtime dispute',
    issue_summary: 'Denied overtime for tour 2',
    grievant_or_class: 'Carrier A',
    current_step_type: 'step_1_initial',
    current_step_status: 'open',
    workspace_status: 'open',
    legacy_case_status: 'open',
    created_at: '2026-07-01T12:00:00Z',
    last_activity_at: '2026-07-20T15:30:00Z',
    closed_at: null,
    reopened_at: null,
    latest_outcome_summary: null,
    latest_outcome_type: null,
    template_availability: null,
    available_actions: ['open_case', 'view_timeline'],
    has_step_progression: true,
    ...overrides,
  }
}

export function makeListResponse(
  cases: SavedCaseSummary[],
  overrides: Partial<SavedCaseListResponse> = {},
): SavedCaseListResponse {
  return {
    count: cases.length,
    total: cases.length,
    limit: 25,
    offset: 0,
    has_more: false,
    order: 'newest_first',
    status_filter: 'all',
    step_filter: null,
    search: null,
    cases,
    payload_mode: 'summary_only',
    ...overrides,
  }
}

/** Full GET /cases/{uuid}/workspace shape used by M2 shell. */
export function makeWorkspace(
  overrides: Partial<CaseWorkspace> = {},
): CaseWorkspace {
  const caseUuid = overrides.case_uuid ?? SAMPLE_CASE_UUID
  const title = overrides.title ?? 'Overtime dispute'
  return {
    case_uuid: caseUuid,
    title,
    user_name: 'Steward Ada',
    local_number: '501',
    initial_question: 'Denied overtime for tour 2',
    known_facts: {
      tour: '2',
      location: 'Station A',
    },
    status: 'open',
    created_at: '2026-07-01T12:00:00Z',
    updated_at: '2026-07-20T15:30:00Z',
    messages: [],
    message_count: 3,
    conversation_history: {
      embedded_in_workspace: false,
      total: 3,
      retrieval: {
        method: 'GET',
        path: `/cases/${caseUuid}/messages`,
        default_limit: 50,
        max_limit: 100,
      },
    },
    workspace_summary: {
      case_uuid: caseUuid,
      title,
      status: 'open',
      workspace_status: 'open',
      current_step_type: 'step_1_initial',
      message_count: 3,
      asset_count: 1,
      has_step_progression: true,
    },
    case_overview: {
      case_uuid: caseUuid,
      case_number: '501',
      employee: 'Carrier A',
      issue: 'Denied overtime for tour 2',
      current_status: 'open',
      current_step: 'step_1_initial',
      explicit_workflow_state: 'case_open',
      current_recommendation: null,
      open_questions: ['Was overtime properly posted?'],
      outstanding_issues: [],
      evidence_count: 0,
      analysis_report_count: 0,
      official_grievance_count: 0,
      management_response_count: 0,
      last_activity_at: '2026-07-20T15:30:00Z',
      assigned_steward: 'Steward Ada',
      reopen_count: 0,
      source: 'case_memory',
    },
    case_memory: {
      schema_version: 'case_memory_v1',
      case_is_system_of_record: true,
      restored_from: 'case_memory',
      facts: {
        tour: '2',
        location: 'Station A',
      },
      status: 'open',
      current_grievance_step: 'step_1_initial',
      workflow: { explicit_state: 'case_open' },
      open_questions: ['Was overtime properly posted?'],
      outstanding_issues: [],
      current_recommendation: null,
      full_transcript_embedded: false,
      full_artifact_bodies_embedded: false,
      reopen_count: 0,
    },
    timeline: [
      {
        event_type: 'case_created',
        title: 'Case created',
        step_type: 'step_1_initial',
        event_timestamp: '2026-07-01T12:00:00Z',
      },
      {
        event_type: 'case_opened',
        title: 'Step 1 opened',
        step_type: 'step_1_initial',
        event_timestamp: '2026-07-01T12:00:01Z',
      },
    ],
    timeline_total_count: 2,
    step_progression: {
      has_step_progression: true,
      workspace_status: 'open',
      current_step_type: 'step_1_initial',
      steps: [
        {
          step_type: 'step_1_initial',
          status: 'open',
        },
      ],
      timeline: [],
    },
    uploaded_assets: [
      {
        asset_uuid: 'asset-1',
        original_filename: 'schedule.pdf',
        asset_category: 'uploaded_document',
      },
    ],
    assets: [
      {
        asset_uuid: 'asset-1',
        original_filename: 'schedule.pdf',
        asset_category: 'uploaded_document',
      },
    ],
    official_artifacts: [],
    case_memory_restored_first: true,
    ai_context_restored: true,
    restore_action_required: false,
    ...overrides,
  }
}

export function makeCaseDetail(
  overrides: Partial<CaseDetail> = {},
): CaseDetail {
  return {
    case_uuid: SAMPLE_CASE_UUID,
    title: 'Overtime dispute',
    user_name: 'Steward Ada',
    local_number: '501',
    initial_question: 'Denied overtime for tour 2',
    known_facts: { tour: '2' },
    status: 'open',
    created_at: '2026-07-01T12:00:00Z',
    updated_at: '2026-07-01T12:00:00Z',
    latest_report_version: null,
    report_summary: null,
    retrieval_gaps_summary: null,
    messages: [],
    latest_report: null,
    report_versions: [],
    ...overrides,
  }
}

export function makeCreateResponse(
  overrides: Partial<CreateCaseResponse> = {},
): CreateCaseResponse {
  return {
    case: makeCaseDetail(overrides.case),
    report_version: null,
  }
}

export function makeFactsResponse(
  overrides: Partial<UpdateFactsResponse> = {},
): UpdateFactsResponse {
  return {
    case_uuid: SAMPLE_CASE_UUID,
    title: 'Overtime dispute',
    user_name: 'Steward Ada',
    local_number: '501',
    initial_question: 'Denied overtime for tour 2',
    known_facts: { tour: '2', location: 'Station A' },
    status: 'open',
    created_at: '2026-07-01T12:00:00Z',
    updated_at: '2026-07-24T18:00:00Z',
    latest_report_version: null,
    report_summary: null,
    retrieval_gaps_summary: null,
    ...overrides,
  }
}

export function makeOpenResponse(
  overrides: Partial<OpenCaseResponse> = {},
): OpenCaseResponse {
  const summary = overrides.case ?? makeSummary()
  return {
    case: summary,
    action_taken: 'already_open',
    message: 'Case is open and ready (source=manual_ui).',
    workspace: makeWorkspace({ case_uuid: summary.case_uuid }),
    ...overrides,
  }
}

export function makeReopenResponse(
  overrides: Partial<ReopenCaseResponse> = {},
): ReopenCaseResponse {
  const summary =
    overrides.case ??
    makeSummary({
      case_uuid: CLOSED_CASE_UUID,
      workspace_status: 'reopened',
      available_actions: ['open_case', 'view_timeline'],
    })
  return {
    case: summary,
    action_taken: 'reopened',
    message: 'Case reopened on the same case workspace; Case Memory restored.',
    source: 'manual_ui',
    workspace: makeWorkspace({
      case_uuid: summary.case_uuid,
      title: summary.title,
      status: 'open',
      workspace_summary: {
        case_uuid: summary.case_uuid,
        title: summary.title,
        status: 'open',
        workspace_status: 'reopened',
        current_step_type: summary.current_step_type,
        message_count: 2,
        asset_count: 0,
      },
    }),
    ...overrides,
  }
}

export function jsonResponse(body: unknown, status = 200): Response {
  return {
    ok: status >= 200 && status < 300,
    status,
    headers: new Headers({ 'content-type': 'application/json' }),
    json: async () => body,
    text: async () => JSON.stringify(body),
  } as Response
}

export function installApiMock(
  handler: (
    input: RequestInfo | URL,
    init?: RequestInit,
  ) => Response | Promise<Response>,
  options: { autoHealth?: boolean } = {},
) {
  const autoHealth = options.autoHealth !== false
  const fetchMock = vi.fn(
    async (input: RequestInfo | URL, init?: RequestInit) => {
      const url =
        typeof input === 'string'
          ? input
          : input instanceof URL
            ? input.toString()
            : input.url
      if (autoHealth && url.includes('/health')) {
        return jsonResponse({ status: 'healthy', service: 'GrievanceHub' })
      }
      return handler(input, init)
    },
  )
  vi.stubGlobal('fetch', fetchMock)
  return fetchMock
}
