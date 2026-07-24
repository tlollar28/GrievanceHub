/**
 * Hand-mirrored from app/schemas/saved_case_schema.py and
 * app/schemas/grievance_template_schema.py (StepLevel / StepType).
 * Verified against FastAPI route signatures and OpenAPI query enums.
 */

export type StepType =
  | 'step_1_initial'
  | 'step_2_appeal'
  | 'step_3_appeal'

export type SavedCaseWorkspaceStatus =
  | 'open'
  | 'closed'
  | 'reopened'
  | 'appealed'
  | 'settled'
  | 'archived'

export type SavedCaseStatusFilter = SavedCaseWorkspaceStatus | 'all'

export type SavedCaseAction =
  | 'open_case'
  | 'reopen_case'
  | 'continue_to_next_step'
  | 'view_timeline'
  | 'create_form_draft'
  | 'settle_case'
  | 'archive_case'

export type ReopenSource = 'manual_ui' | 'ai_command' | 'system'

export type SavedCaseOrder = 'newest_first' | 'oldest_first'

export type SavedCaseTemplateAvailability = {
  step_type: StepType | null
  template_available: boolean
  template_id: string | null
  availability_status:
    | 'available'
    | 'unavailable'
    | 'deferred_separate_form_required'
    | 'unconfirmed_pending_steward_confirmation'
    | null
}

export type SavedCaseSummary = {
  case_id: number
  case_uuid: string
  case_number: string | null
  title: string | null
  issue_summary: string | null
  grievant_or_class: string | null
  current_step_type: StepType | null
  current_step_status: string | null
  workspace_status: SavedCaseWorkspaceStatus
  legacy_case_status: string
  created_at: string | null
  last_activity_at: string | null
  closed_at: string | null
  reopened_at: string | null
  latest_outcome_summary: string | null
  latest_outcome_type: string | null
  template_availability: SavedCaseTemplateAvailability | null
  available_actions: SavedCaseAction[]
  has_step_progression: boolean
}

export type SavedCaseListResponse = {
  count: number
  total: number | null
  limit: number | null
  offset: number | null
  has_more: boolean
  order: SavedCaseOrder
  status_filter: SavedCaseStatusFilter
  step_filter: StepType | null
  search: string | null
  cases: SavedCaseSummary[]
  payload_mode: 'summary_only'
}

export type OpenCaseRequest = {
  source?: ReopenSource
}

export type ReopenCaseRequest = {
  reason?: string | null
  reopened_by?: string | null
  source?: ReopenSource
}

export type OpenCaseResponse = {
  case: SavedCaseSummary
  action_taken: 'already_open' | 'opened' | 'closed_requires_reopen'
  message: string
  workspace: CaseWorkspaceBootstrap | null
}

export type ReopenCaseResponse = {
  case: SavedCaseSummary
  action_taken: 'reopened' | 'already_open'
  message: string
  source: ReopenSource
  workspace: CaseWorkspaceBootstrap | null
}

/** Lean subset of GET /cases/{uuid}/workspace used by the M1 entry route. */
export type CaseWorkspaceBootstrap = {
  case_uuid: string
  title: string | null
  status: string
  message_count?: number
  workspace_summary?: {
    case_uuid: string
    title: string | null
    status: string
    workspace_status?: string | null
    current_step_type?: string | null
    message_count?: number
    asset_count?: number
  }
  overview?: {
    case_uuid?: string
    current_status?: string
    issue?: string | null
    title?: string | null
  }
}

export type ListSavedCasesParams = {
  status?: SavedCaseStatusFilter
  step?: StepType | null
  search?: string | null
  order?: SavedCaseOrder
  limit?: number
  offset?: number
}
