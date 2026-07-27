/**
 * Hand-mirrored from app/schemas/case_workflow_schema.py,
 * app/schemas/case_memory_schema.py (RecordStepOutcomeRequest, CaseCloseRequest,
 * CaseSettleRequest), and OutcomeType in case_step_progression_schema.py.
 * Verified against FastAPI routes in app/api/routes/cases.py.
 */

import type { CaseWorkspace } from './workspace'
import type { SavedCaseSummary, StepType } from './savedCases'

/** Explicit FSM states from CaseWorkflowService / WorkflowState. */
export type WorkflowState =
  | 'case_open'
  | 'step_1_analysis'
  | 'step_1_draft'
  | 'step_1_awaiting_steward_review'
  | 'step_1_official'
  | 'step_1_awaiting_management_response'
  | 'step_1_response_received'
  | 'step_1_decision_required'
  | 'step_1_resolved'
  | 'step_1_appealed'
  | 'step_2_analysis'
  | 'step_2_draft'
  | 'step_2_awaiting_steward_review'
  | 'step_2_official'
  | 'step_2_awaiting_management_response'
  | 'step_2_response_received'
  | 'step_2_decision_required'
  | 'step_2_resolved'
  | 'step_2_appealed'
  | 'step_3_analysis'
  | 'step_3_draft'
  | 'step_3_awaiting_steward_review'
  | 'step_3_official'
  | 'step_3_awaiting_management_response'
  | 'step_3_response_received'
  | 'step_3_decision_required'
  | 'step_3_resolved'
  | 'settled'
  | 'closed'
  | 'reopened'
  | (string & {})

export type OutcomeType =
  | 'pending'
  | 'resolved'
  | 'granted'
  | 'partially_granted'
  | 'denied'
  | 'withdrawn'
  | 'settled'
  | 'appealed'
  | 'closed_no_appeal'
  | 'unknown'

/** GET /cases/{case_uuid}/workflow */
export type WorkflowStateView = {
  case_uuid: string
  explicit_state: WorkflowState
  current_grievance_step: string | null
  case_status: string | null
  inferred: boolean
  inference_confidence: 'confirmed' | 'inferred' | 'unknown'
  permitted_next_states: string[]
  updated_at: string | null
}

/** POST /cases/{case_uuid}/workflow/transitions */
export type WorkflowTransitionInput = {
  to_state: WorkflowState | string
  reason?: string | null
  actor_id?: string | null
  grievance_step?: string | null
  allow_authorized_override?: boolean
  source_type?: string | null
  source_uuid?: string | null
  metadata?: Record<string, unknown>
}

/** POST /cases/{case_uuid}/outcomes — RecordStepOutcomeRequest */
export type RecordStepOutcomeRequest = {
  step_type?: string | null
  outcome_type?: OutcomeType | string
  decision_summary?: string | null
  decision_date?: string | null
  steward_notes?: string | null
  close_case?: boolean
  close_step?: boolean
  appeal_to_next_step?: boolean
  decision_document_refs?: string[]
  resolution_type?: string | null
  closed_by?: string | null
}

export type CaseStepOutcomeRecord = {
  outcome_id: string
  step_type: string
  outcome_type: OutcomeType | string
  decision_summary: string | null
  decision_date: string | null
  decision_maker_name: string | null
  decision_maker_title: string | null
  decision_document_refs: string[]
  steward_notes: string | null
  step_closed: boolean
  case_closed: boolean
  appeal_requested: boolean
  next_step_target: StepType | string | null
  recorded_at: string
}

export type CaseStepStageSummary = {
  step_type: string
  step_number?: number
  status: string
  is_closed?: boolean
  was_reopened?: boolean
  template_id?: string | null
  template_availability?: string | null
  outcomes?: CaseStepOutcomeRecord[]
  opened_at?: string | null
  closed_at?: string | null
}

/** Response envelope from POST /cases/{uuid}/outcomes */
export type RecordStepOutcomeResponse = {
  case_uuid: string
  outcome: CaseStepOutcomeRecord
  step: CaseStepStageSummary
  workflow: WorkflowStateView
  case_overview: Record<string, unknown>
  workspace: CaseWorkspace | Record<string, unknown>
}

/** POST /cases/saved/{uuid}/close — CaseCloseRequest */
export type CaseCloseRequest = {
  outcome: string
  outcome_notes?: string | null
  resolution_type: string
  close_date?: string | null
  closed_by?: string | null
  final_grievance_step?: string | null
  supporting_document_refs?: string[]
}

export type CaseCloseResponse = {
  case: SavedCaseSummary
  action_taken: 'closed'
  message: string
  closure: Record<string, unknown>
  workspace: CaseWorkspace | Record<string, unknown>
}

/** POST /cases/saved/{uuid}/settle — CaseSettleRequest */
export type CaseSettleRequest = {
  settlement_notes?: string | null
  settlement_date?: string | null
  settlement_document_refs?: string[]
  settlement_amount?: number | null
  settled_by?: string | null
}

export type CaseSettleResponse = {
  case: SavedCaseSummary
  action_taken: 'settled'
  message: string
  settlement: Record<string, unknown>
  workspace: CaseWorkspace | Record<string, unknown>
}

/**
 * POST /cases/saved/{uuid}/archive
 * Backend accepts UpdateStatusRequest | None. When a JSON body is sent,
 * `status` is required (`archived`). Prefer omitting the body entirely when
 * no reason is provided.
 */
export type CaseArchiveRequest = {
  status: 'archived'
  reason?: string | null
}

export type CaseArchiveResponse = {
  case: SavedCaseSummary
  action_taken: 'archived'
  message: string
  workspace: CaseWorkspace | Record<string, unknown>
}

export const OUTCOME_TYPE_VALUES: readonly OutcomeType[] = [
  'pending',
  'resolved',
  'granted',
  'partially_granted',
  'denied',
  'withdrawn',
  'settled',
  'appealed',
  'closed_no_appeal',
  'unknown',
] as const
