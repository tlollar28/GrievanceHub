/**
 * Hand-mirrored from app/schemas/case_workspace_action_schema.py and
 * FollowUpCitation in app/schemas/follow_up_schema.py.
 * Citations on CaseInteractionResponse are typed as list[dict] in OpenAPI;
 * FollowUpCitation is the verified runtime shape.
 */

export type InteractionSource = 'manual_ui' | 'ai_command' | 'system'

export type RetrievalStatus = 'ok' | 'empty' | 'failed' | 'skipped'

export type CaseMemoryUpdateStatus =
  | 'updated'
  | 'projection_failed'
  | 'failed'
  | 'unknown'
  | 'not_applicable'

export type WorkspaceActionExecutionStatus =
  | 'not_implemented_in_w1'
  | 'prerequisites_not_met'
  | 'case_not_found'
  | 'invalid_request'
  | 'accepted'
  | 'completed'

export type GroundingProvenance =
  | 'retrieved_passage'
  | 'saved_report_authority'
  | 'ungrounded'

export type InteractionCitation = {
  document_type?: string
  document_name?: string
  article_or_section?: string
  page?: number | null
  quote?: string
  grounded?: boolean
  grounding_provenance?: GroundingProvenance | string
  grounding_passage_index?: number | null
  grounding_authority_index?: number | null
  [key: string]: unknown
}

export type CaseInteractionRequest = {
  message?: string | null
  clarification?: string | null
  fact_updates?: Record<string, unknown> | null
  upload_refs?: string[]
  source?: InteractionSource
  pinned_report_version?: number | null
}

export type CaseInteractionMessageSummary = {
  id: number
  role: string
  content: string
  metadata?: Record<string, unknown> | null
  created_at?: string | null
}

export type WorkspaceActionPrerequisite = {
  code: string
  message: string
  resolved_in_phase?: string | null
  details?: Record<string, unknown> | null
}

export type WorkspaceActionAvailability = {
  action: string
  available: boolean
  reason?: string | null
  steward_visible?: boolean
  missing_prerequisites?: WorkspaceActionPrerequisite[]
  current_step_type?: string | null
  template_id?: string | null
  template_availability?: string | null
}

export type AnalysisUpdateResult = {
  steward_action_label?: string | null
  interaction_saved?: boolean
  prior_conversation_preserved?: boolean
  facts_updated?: boolean
  ai_response_persisted?: boolean
  case_memory_update_status?: CaseMemoryUpdateStatus
  prior_report_version_id?: number | null
  prior_report_version_number?: number | null
  new_report_version_id?: number | null
  new_report_version_number?: number | null
  is_current_analysis?: boolean
  older_versions_retained?: boolean
  trigger_message_id?: number | null
  trigger_metadata?: Record<string, unknown> | null
  timeline_events?: unknown[]
  message?: string
}

export type CaseInteractionResponse = {
  case_uuid: string
  status: WorkspaceActionExecutionStatus
  message: string
  workspace_current?: boolean
  user_message?: CaseInteractionMessageSummary | null
  assistant_message?: CaseInteractionMessageSummary | null
  ai_answer?: string | null
  answer_type?: string | null
  citations?: InteractionCitation[]
  disclosures?: string[]
  facts_needed?: string[]
  retrieval_status?: RetrievalStatus | null
  retrieval_error?: boolean
  case_memory_update_status?: CaseMemoryUpdateStatus
  prior_report_version_id?: number | null
  prior_report_version_number?: number | null
  current_report_version_id?: number | null
  current_report_version_number?: number | null
  analysis_update?: AnalysisUpdateResult | null
  available_actions?: WorkspaceActionAvailability[]
  generate_grievance_available?: boolean
  missing_prerequisites?: WorkspaceActionPrerequisite[]
  timeline_events?: unknown[]
  grievance_draft_created?: boolean
  generation_snapshot_persisted?: boolean
  export_attempted?: boolean
  analysis_versions_created?: number
}
