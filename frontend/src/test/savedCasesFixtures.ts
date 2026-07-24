import { vi } from 'vitest'
import type {
  CaseWorkspaceBootstrap,
  OpenCaseResponse,
  ReopenCaseResponse,
  SavedCaseListResponse,
  SavedCaseSummary,
} from '../api/types/savedCases'

export const SAMPLE_CASE_UUID = '11111111-1111-4111-8111-111111111111'
export const CLOSED_CASE_UUID = '22222222-2222-4222-8222-222222222222'

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

export function makeWorkspace(
  overrides: Partial<CaseWorkspaceBootstrap> = {},
): CaseWorkspaceBootstrap {
  return {
    case_uuid: SAMPLE_CASE_UUID,
    title: 'Overtime dispute',
    status: 'open',
    message_count: 3,
    workspace_summary: {
      case_uuid: SAMPLE_CASE_UUID,
      title: 'Overtime dispute',
      status: 'open',
      workspace_status: 'open',
      current_step_type: 'step_1_initial',
      message_count: 3,
      asset_count: 1,
    },
    overview: {
      case_uuid: SAMPLE_CASE_UUID,
      current_status: 'open',
      issue: 'Denied overtime for tour 2',
    },
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
