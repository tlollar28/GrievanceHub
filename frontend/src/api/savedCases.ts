import { apiRequest } from './client'
import type {
  ListSavedCasesParams,
  OpenCaseRequest,
  OpenCaseResponse,
  ReopenCaseRequest,
  ReopenCaseResponse,
  SavedCaseListResponse,
  SavedCaseSummary,
} from './types/savedCases'

export { getCaseWorkspace } from './workspace'

function buildListQuery(params: ListSavedCasesParams = {}): string {
  const searchParams = new URLSearchParams()
  searchParams.set('status', params.status ?? 'all')
  searchParams.set('order', params.order ?? 'newest_first')
  searchParams.set('limit', String(params.limit ?? 50))
  searchParams.set('offset', String(params.offset ?? 0))

  if (params.step) {
    searchParams.set('step', params.step)
  }
  if (params.search && params.search.trim().length > 0) {
    searchParams.set('search', params.search.trim())
  }

  return searchParams.toString()
}

/** GET /cases/saved — mirrors FastAPI list_saved_cases. */
export function listSavedCases(
  params: ListSavedCasesParams = {},
  signal?: AbortSignal,
): Promise<SavedCaseListResponse> {
  const query = buildListQuery(params)
  return apiRequest<SavedCaseListResponse>(`/cases/saved?${query}`, { signal })
}

/** GET /cases/saved/{case_uuid} */
export function getSavedCase(
  caseUuid: string,
  signal?: AbortSignal,
): Promise<SavedCaseSummary> {
  return apiRequest<SavedCaseSummary>(`/cases/saved/${caseUuid}`, { signal })
}

/** POST /cases/saved/{case_uuid}/open */
export function openSavedCase(
  caseUuid: string,
  body: OpenCaseRequest = { source: 'manual_ui' },
  signal?: AbortSignal,
): Promise<OpenCaseResponse> {
  return apiRequest<OpenCaseResponse>(`/cases/saved/${caseUuid}/open`, {
    method: 'POST',
    body,
    signal,
  })
}

/** POST /cases/saved/{case_uuid}/reopen */
export function reopenSavedCase(
  caseUuid: string,
  body: ReopenCaseRequest = { source: 'manual_ui' },
  signal?: AbortSignal,
): Promise<ReopenCaseResponse> {
  return apiRequest<ReopenCaseResponse>(`/cases/saved/${caseUuid}/reopen`, {
    method: 'POST',
    body,
    signal,
  })
}
