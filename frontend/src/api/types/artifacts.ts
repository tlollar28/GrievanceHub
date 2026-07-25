/**
 * Hand-mirrored from app/schemas/case_saved_artifact_schema.py,
 * case_history_context_schema.py, saved_case_schema.py, and
 * case_step_progression_schema.py.
 * OpenAPI may be incomplete — Pydantic / service serialization is source of truth.
 */

import type { CaseSavedArtifactSummary } from './reports'

export type {
  BinaryExportResult,
  CaseSavedArtifactSummary,
  PdfStatus,
  SaveAndPrintResponse,
} from './reports'

export type ArtifactType = 'analysis_report' | 'grievance_form'

export type ArtifactTypeFilter = ArtifactType | 'all'

export type ArtifactSortOrder = 'newest' | 'oldest'

export type HistoryOrder = 'oldest_first' | 'newest_first'

export type CaseSavedArtifactDetail = CaseSavedArtifactSummary & {
  content_json: Record<string, unknown>
  pdf_download_path?: string | null
}

export type CaseSavedArtifactListResponse = {
  case_uuid: string
  count: number
  artifacts: CaseSavedArtifactSummary[]
  groups?: {
    analysis_reports?: CaseSavedArtifactSummary[]
    grievances?: CaseSavedArtifactSummary[]
    management_responses?: CaseSavedArtifactSummary[]
    evidence?: CaseSavedArtifactSummary[]
    other?: CaseSavedArtifactSummary[]
    [key: string]: CaseSavedArtifactSummary[] | undefined
  }
}

export type ListArtifactsParams = {
  artifact_type?: ArtifactType | null
}

/** Steward-facing Official Case Record item (GET .../saved/{uuid}/history). */
export type CaseHistoryItem = {
  event_id: string
  event_type: string
  title: string
  details?: string | null
  event_timestamp: string
  icon?: string
  clickable?: boolean
  artifact_uuid?: string | null
  artifact_type?: string | null
  asset_uuid?: string | null
  report_version_number?: number | null
  draft_uuid?: string | null
  retrieval_path?: string | null
  context_path?: string | null
  record_class?: 'working_draft' | 'official_record' | 'lifecycle' | 'other' | string
  display_label?: string | null
}

export type CaseHistoryResponse = {
  case_uuid: string
  label?: string
  count: number
  order: HistoryOrder
  events: CaseHistoryItem[]
}

export type ListCaseHistoryParams = {
  order?: HistoryOrder
  limit?: number
}

/** Broader timeline event (GET .../saved/{uuid}/timeline). */
export type CaseTimelineEventReferences = {
  report_version_id?: number | null
  report_version_number?: number | null
  follow_up_message_ids?: number[]
  form_draft_id?: string | null
  upload_refs?: string[]
  outcome_id?: string | null
  prior_step_type?: string | null
  next_step_type?: string | null
  export_ref?: string | null
}

export type CaseTimelineEvent = {
  event_id: string
  case_uuid: string
  step_type?: string | null
  event_type: string
  event_timestamp: string
  title: string
  details?: string | null
  references?: CaseTimelineEventReferences
}

export type SavedCaseTimelineResponse = {
  case_uuid: string
  order: HistoryOrder
  count: number
  events: CaseTimelineEvent[]
}

export type ListCaseTimelineParams = {
  order?: HistoryOrder
}

export type HistoricalConversationWindow = {
  message_ids?: number[]
  messages?: Array<Record<string, unknown>>
  bounded?: boolean
  full_transcript_replayed?: boolean
  window_size?: number
}

/** GET /cases/{uuid}/history/{event_id}/context */
export type CaseHistoryContextResponse = {
  case_uuid: string
  event_id: string
  event_details: Record<string, unknown>
  related_artifact?: Record<string, unknown> | null
  related_conversation?: HistoricalConversationWindow
  related_evidence?: Array<Record<string, unknown>>
  related_workflow_state?: Record<string, unknown> | null
  related_decisions?: Array<Record<string, unknown>>
  related_recommendation?: Record<string, unknown> | null
  previous_event?: Record<string, unknown> | null
  next_event?: Record<string, unknown> | null
  retrieval_references?: Record<string, string>
  record_class?: string
  mutates_current_memory?: boolean
  historical_focus_ref?: Record<string, unknown> | null
  unavailable_fields?: string[]
}

export type HistoryContextParams = {
  conversation_window?: number
}

/** POST /cases/{uuid}/artifacts/compare */
export type CompareArtifactsRequest = {
  left_artifact_uuid?: string | null
  right_artifact_uuid?: string | null
  artifact_type?: ArtifactType | null
  left_version?: number | null
  right_version?: number | null
}

export type ArtifactCompareResponse = {
  case_uuid: string
  artifact_type: ArtifactType | string
  left: CaseSavedArtifactDetail
  right: CaseSavedArtifactDetail
  changed_summary_keys: string[]
  left_only_summary_keys: string[]
  right_only_summary_keys: string[]
  version_delta?: number | null
  retrieval_note?: string
}
