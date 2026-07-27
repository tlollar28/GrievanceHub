/**
 * Hand-mirrored from CaseService.get_case_workspace and CaseOverview /
 * CaseMemory AI foundation shapes. OpenAPI response_model is omitted on the
 * workspace route — Pydantic/service implementation is the source of truth.
 */

import type { KnownFacts } from './cases'

export type WorkspaceSummary = {
  case_uuid: string
  title: string | null
  status: string
  has_step_progression?: boolean
  workspace_status?: string | null
  current_step_type?: string | null
  latest_report_version?: number | null
  message_count?: number
  asset_count?: number
  report_summary?: unknown
}

export type CaseOverview = {
  case_uuid: string
  employee?: string | null
  case_number?: string | null
  issue?: string | null
  current_status: string
  current_step?: string | null
  explicit_workflow_state?: string | null
  current_recommendation?: string | null
  recommendation_rationale?: string | null
  recommendation_status?: string | null
  ai_recommendation?: Record<string, unknown> | null
  steward_decision?: Record<string, unknown> | null
  supporting_evidence_count?: number
  supporting_evidence_refs?: string[]
  open_questions?: string[]
  outstanding_issues?: string[]
  evidence_count?: number
  analysis_report_count?: number
  official_grievance_count?: number
  management_response_count?: number
  management_response_status?: string | null
  last_activity_at?: string | null
  assigned_steward?: string | null
  settlement_status?: string | null
  outcome_status?: string | null
  close_date?: string | null
  reopen_count?: number
  latest_official_report_version?: number | null
  latest_official_grievance_version?: number | null
  latest_official_report_title?: string | null
  latest_official_grievance_title?: string | null
  source?: 'case_memory' | string
}

/** Bounded Case Memory foundation embedded in workspace (not a transcript). */
export type CaseMemoryFoundation = {
  schema_version?: string
  case_is_system_of_record?: boolean
  restored_from?: string
  identity_and_facts?: Record<string, unknown>
  facts?: KnownFacts
  status?: string | null
  status_and_lifecycle?: Record<string, unknown>
  current_grievance_step?: string | null
  workflow?: Record<string, unknown>
  workflow_state?: Record<string, unknown>
  open_questions?: string[]
  outstanding_issues?: string[]
  current_recommendation?: string | null
  ai_recommendation?: Record<string, unknown> | null
  conversation_summaries?: unknown[]
  full_transcript_embedded?: boolean
  full_artifact_bodies_embedded?: boolean
  reopen_count?: number
  [key: string]: unknown
}

export type WorkspaceTimelineEvent = {
  event_type?: string
  title?: string
  step_type?: string | null
  event_timestamp?: string | null
  created_at?: string | null
  [key: string]: unknown
}

export type WorkspaceAssetSummary = {
  asset_uuid?: string
  original_filename?: string | null
  filename?: string | null
  asset_category?: string | null
  created_at?: string | null
  [key: string]: unknown
}

export type OfficialArtifactSummary = {
  artifact_uuid?: string
  artifact_type?: string | null
  title?: string | null
  version_number?: number | null
  [key: string]: unknown
}

export type StepProgressionPayload = {
  has_step_progression?: boolean
  workspace_status?: string | null
  current_step_type?: string | null
  steps?: unknown[]
  outcomes?: unknown[]
  timeline?: WorkspaceTimelineEvent[]
  created_at?: string | null
  updated_at?: string | null
  closed_at?: string | null
  reopened_at?: string | null
  [key: string]: unknown
}

/**
 * Lean GET /cases/{case_uuid}/workspace aggregate.
 * messages is always [] — full transcript is a separate endpoint (M3).
 */
export type CaseWorkspace = {
  case_uuid: string
  title: string | null
  user_name: string | null
  local_number: string | null
  initial_question: string | null
  known_facts: KnownFacts | null
  status: string
  created_at: string | null
  updated_at: string | null
  messages: unknown[]
  message_count: number
  conversation_history?: {
    embedded_in_workspace: boolean
    total: number
    retrieval?: {
      method: string
      path: string
      default_limit?: number
      max_limit?: number
    }
  }
  workspace_summary: WorkspaceSummary
  case_overview: CaseOverview
  case_memory: CaseMemoryFoundation
  timeline: WorkspaceTimelineEvent[]
  timeline_total_count?: number
  step_progression?: StepProgressionPayload
  grievance_progression?: StepProgressionPayload
  uploaded_assets?: WorkspaceAssetSummary[]
  assets?: WorkspaceAssetSummary[]
  official_artifacts?: OfficialArtifactSummary[]
  case_history?: unknown
  available_actions?: unknown[]
  case_memory_restored_first?: boolean
  ai_context_restored?: boolean
  restore_action_required?: boolean
  /** Present on some lean/cached payloads; prefer case_overview. */
  overview?: Partial<CaseOverview> & { title?: string | null }
  [key: string]: unknown
}
