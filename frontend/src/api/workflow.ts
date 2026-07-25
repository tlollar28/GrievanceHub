import { apiRequest } from './client'
import type {
  CaseArchiveRequest,
  CaseArchiveResponse,
  CaseCloseRequest,
  CaseCloseResponse,
  CaseSettleRequest,
  CaseSettleResponse,
  RecordStepOutcomeRequest,
  RecordStepOutcomeResponse,
  WorkflowStateView,
  WorkflowTransitionInput,
} from './types/workflow'

/** GET /cases/{case_uuid}/workflow */
export function getCaseWorkflow(
  caseUuid: string,
  signal?: AbortSignal,
): Promise<WorkflowStateView> {
  return apiRequest<WorkflowStateView>(`/cases/${caseUuid}/workflow`, {
    signal,
  })
}

/**
 * POST /cases/{case_uuid}/workflow/transitions
 * Prefer outcomes / saved-case lifecycle routes for steward actions.
 * Exposed for verified edge cases only — not a generic FSM button surface.
 */
export function transitionCaseWorkflow(
  caseUuid: string,
  body: WorkflowTransitionInput,
  signal?: AbortSignal,
): Promise<WorkflowStateView> {
  return apiRequest<WorkflowStateView>(
    `/cases/${caseUuid}/workflow/transitions`,
    {
      method: 'POST',
      body,
      signal,
    },
  )
}

/** POST /cases/{case_uuid}/outcomes */
export function recordCaseOutcome(
  caseUuid: string,
  body: RecordStepOutcomeRequest,
  signal?: AbortSignal,
): Promise<RecordStepOutcomeResponse> {
  return apiRequest<RecordStepOutcomeResponse>(`/cases/${caseUuid}/outcomes`, {
    method: 'POST',
    body,
    signal,
  })
}

/** POST /cases/saved/{case_uuid}/close */
export function closeSavedCase(
  caseUuid: string,
  body: CaseCloseRequest,
  signal?: AbortSignal,
): Promise<CaseCloseResponse> {
  return apiRequest<CaseCloseResponse>(`/cases/saved/${caseUuid}/close`, {
    method: 'POST',
    body,
    signal,
  })
}

/** POST /cases/saved/{case_uuid}/settle */
export function settleSavedCase(
  caseUuid: string,
  body: CaseSettleRequest = {},
  signal?: AbortSignal,
): Promise<CaseSettleResponse> {
  return apiRequest<CaseSettleResponse>(`/cases/saved/${caseUuid}/settle`, {
    method: 'POST',
    body,
    signal,
  })
}

/** POST /cases/saved/{case_uuid}/archive */
export function archiveSavedCase(
  caseUuid: string,
  body?: CaseArchiveRequest | null,
  signal?: AbortSignal,
): Promise<CaseArchiveResponse> {
  const options: {
    method: string
    body?: CaseArchiveRequest
    signal?: AbortSignal
  } = {
    method: 'POST',
    signal,
  }
  if (body) {
    options.body = body
  }
  return apiRequest<CaseArchiveResponse>(
    `/cases/saved/${caseUuid}/archive`,
    options,
  )
}
