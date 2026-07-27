/**
 * Hand-mirrored from CreateCaseRequest / UpdateFactsRequest in
 * app/api/routes/cases.py and CaseService.serialize_case_list_summary.
 */

export type KnownFacts = Record<string, unknown>

export type CreateCaseRequest = {
  question: string
  user_name?: string | null
  local_number?: string | null
  known_facts?: KnownFacts | null
}

export type CaseListSummary = {
  case_uuid: string
  title: string | null
  user_name: string | null
  local_number: string | null
  initial_question: string | null
  known_facts: KnownFacts | null
  status: string
  created_at: string | null
  updated_at: string | null
  latest_report_version: number | null
  report_summary: unknown
  retrieval_gaps_summary: unknown
}

export type CaseMessageSummary = {
  id: number
  role: string
  content: string
  metadata: unknown
  created_at: string | null
}

export type CaseDetail = CaseListSummary & {
  messages: CaseMessageSummary[]
  latest_report: unknown
  report_versions: unknown[]
}

/** POST /cases/ — creates case without auto-analysis. */
export type CreateCaseResponse = {
  case: CaseDetail
  report_version: null
}

/** PATCH /cases/{case_uuid}/facts */
export type UpdateFactsRequest = {
  known_facts: KnownFacts
}

/** Facts update returns serialize_case_list_summary (not workspace). */
export type UpdateFactsResponse = CaseListSummary
