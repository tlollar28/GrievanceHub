import { apiBinaryRequest, apiRequest } from './client'
import type {
  ArtifactCompareResponse,
  BinaryExportResult,
  CaseHistoryContextResponse,
  CaseHistoryResponse,
  CaseSavedArtifactDetail,
  CaseSavedArtifactListResponse,
  CompareArtifactsRequest,
  HistoryContextParams,
  ListArtifactsParams,
  ListCaseHistoryParams,
  ListCaseTimelineParams,
  SavedCaseTimelineResponse,
} from './types/artifacts'

function artifactsQuery(params: ListArtifactsParams = {}): string {
  if (!params.artifact_type) return ''
  const search = new URLSearchParams()
  search.set('artifact_type', params.artifact_type)
  return `?${search.toString()}`
}

function historyQuery(params: ListCaseHistoryParams = {}): string {
  const search = new URLSearchParams()
  search.set('order', params.order ?? 'newest_first')
  if (params.limit != null) {
    search.set('limit', String(params.limit))
  }
  return `?${search.toString()}`
}

function timelineQuery(params: ListCaseTimelineParams = {}): string {
  const search = new URLSearchParams()
  search.set('order', params.order ?? 'newest_first')
  return `?${search.toString()}`
}

function contextQuery(params: HistoryContextParams = {}): string {
  if (params.conversation_window == null) return ''
  const search = new URLSearchParams()
  search.set('conversation_window', String(params.conversation_window))
  return `?${search.toString()}`
}

/**
 * GET /cases/{case_uuid}/artifacts
 * Optional artifact_type filter: analysis_report | grievance_form.
 */
export function listCaseArtifacts(
  caseUuid: string,
  params: ListArtifactsParams = {},
  signal?: AbortSignal,
): Promise<CaseSavedArtifactListResponse> {
  return apiRequest<CaseSavedArtifactListResponse>(
    `/cases/${caseUuid}/artifacts${artifactsQuery(params)}`,
    { signal },
  )
}

/**
 * GET /cases/{case_uuid}/artifacts/{artifact_uuid}
 */
export function getCaseArtifact(
  caseUuid: string,
  artifactUuid: string,
  signal?: AbortSignal,
): Promise<CaseSavedArtifactDetail> {
  return apiRequest<CaseSavedArtifactDetail>(
    `/cases/${caseUuid}/artifacts/${artifactUuid}`,
    { signal },
  )
}

/**
 * GET /cases/{case_uuid}/artifacts/{artifact_uuid}/pdf
 */
export function fetchCaseArtifactPdf(
  caseUuid: string,
  artifactUuid: string,
  signal?: AbortSignal,
): Promise<BinaryExportResult> {
  return apiBinaryRequest(
    `/cases/${caseUuid}/artifacts/${artifactUuid}/pdf`,
    {
      accept: 'application/pdf',
      signal,
    },
  )
}

/**
 * POST /cases/{case_uuid}/artifacts/compare
 * Comparison is read-only — creates no new official artifact.
 */
export function compareCaseArtifacts(
  caseUuid: string,
  body: CompareArtifactsRequest,
  signal?: AbortSignal,
): Promise<ArtifactCompareResponse> {
  return apiRequest<ArtifactCompareResponse>(
    `/cases/${caseUuid}/artifacts/compare`,
    {
      method: 'POST',
      body,
      signal,
    },
  )
}

/**
 * GET /cases/saved/{case_uuid}/history
 * Steward-facing Official Case Record.
 */
export function listCaseHistory(
  caseUuid: string,
  params: ListCaseHistoryParams = {},
  signal?: AbortSignal,
): Promise<CaseHistoryResponse> {
  return apiRequest<CaseHistoryResponse>(
    `/cases/saved/${caseUuid}/history${historyQuery(params)}`,
    { signal },
  )
}

/**
 * GET /cases/saved/{case_uuid}/timeline
 * Broader case timeline (not a substitute for Official Case Record).
 */
export function listCaseTimeline(
  caseUuid: string,
  params: ListCaseTimelineParams = {},
  signal?: AbortSignal,
): Promise<SavedCaseTimelineResponse> {
  return apiRequest<SavedCaseTimelineResponse>(
    `/cases/saved/${caseUuid}/timeline${timelineQuery(params)}`,
    { signal },
  )
}

/**
 * GET /cases/{case_uuid}/history/{event_id}/context
 * Read-only jump-to-context for an Official Case Record event.
 */
export function getHistoryContext(
  caseUuid: string,
  eventId: string,
  params: HistoryContextParams = {},
  signal?: AbortSignal,
): Promise<CaseHistoryContextResponse> {
  return apiRequest<CaseHistoryContextResponse>(
    `/cases/${caseUuid}/history/${eventId}/context${contextQuery(params)}`,
    { signal },
  )
}
