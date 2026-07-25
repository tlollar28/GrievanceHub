import { apiRequest } from './client'
import type {
  CreateCaseRequest,
  CreateCaseResponse,
  UpdateFactsRequest,
  UpdateFactsResponse,
} from './types/cases'

/** POST /cases/ — create without auto-analysis or first chat turn. */
export function createCase(
  body: CreateCaseRequest,
  signal?: AbortSignal,
): Promise<CreateCaseResponse> {
  return apiRequest<CreateCaseResponse>('/cases/', {
    method: 'POST',
    body,
    signal,
  })
}

/** PATCH /cases/{case_uuid}/facts — replaces known_facts; returns case summary. */
export function updateCaseFacts(
  caseUuid: string,
  body: UpdateFactsRequest,
  signal?: AbortSignal,
): Promise<UpdateFactsResponse> {
  return apiRequest<UpdateFactsResponse>(`/cases/${caseUuid}/facts`, {
    method: 'PATCH',
    body,
    signal,
  })
}
