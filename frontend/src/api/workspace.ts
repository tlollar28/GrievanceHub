import { apiRequest } from './client'
import type { CaseWorkspace } from './types/workspace'

/** GET /cases/{case_uuid}/workspace — lean restore (no full transcript). */
export function getCaseWorkspace(
  caseUuid: string,
  signal?: AbortSignal,
): Promise<CaseWorkspace> {
  return apiRequest<CaseWorkspace>(`/cases/${caseUuid}/workspace`, {
    signal,
  })
}
