import { apiRequest } from './client'
import type {
  CaseInteractionRequest,
  CaseInteractionResponse,
} from './types/interactions'

/**
 * POST /cases/{case_uuid}/interactions — canonical conversational turn.
 * Does not create analysis reports, grievances, or official artifacts.
 */
export function submitCaseInteraction(
  caseUuid: string,
  body: CaseInteractionRequest,
  signal?: AbortSignal,
): Promise<CaseInteractionResponse> {
  return apiRequest<CaseInteractionResponse>(
    `/cases/${caseUuid}/interactions`,
    {
      method: 'POST',
      body,
      signal,
    },
  )
}
