/**
 * Hand-mirrored from app/schemas/case_workspace_action_schema.py and
 * app/schemas/case_saved_artifact_schema.py (grievance contracts).
 * OpenAPI may be incomplete — Pydantic / service serialization is source of truth.
 */

import type {
  CaseSavedArtifactSummary,
  WorkspaceActionAvailability,
  WorkspaceActionPrerequisite,
} from './reports'

export type {
  CaseSavedArtifactSummary,
  SaveAndPrintResponse,
  SaveAndPrintStatus,
  PdfStatus,
  BinaryExportResult,
  WorkspaceActionAvailability,
  WorkspaceActionPrerequisite,
} from './reports'

/** Official templates supported by the W6 steward grievance UI. */
export type SupportedGrievanceTemplateId =
  | 'official_grievance_worksheet_step_1'
  | 'official_standard_grievance_form_step_2'

export type GrievanceStepType =
  | 'step_1_initial'
  | 'step_2_appeal'
  | 'step_3_appeal'
  | string

export type DraftStatus =
  | 'draft'
  | 'pending_required_fields'
  | 'ready_for_steward_review'
  | string

/** Flat field map returned by generate_grievance (string scalars). */
export type GrievanceFieldValues = Record<string, string | unknown>

export type GrievanceGenerationResult = {
  context_saved_first?: boolean
  analysis_reflected_latest_context?: boolean
  draft_created?: boolean
  draft_id?: string | null
  draft_version?: number | null
  template_id?: string | null
  step_type?: GrievanceStepType | null
  draft_status?: DraftStatus | null
  editable?: boolean
  field_values?: GrievanceFieldValues
  official_artifact_created?: boolean
  export_attempted?: boolean
  message?: string
  [key: string]: unknown
}

/** POST /cases/{uuid}/actions body for generate_grievance. */
export type GenerateGrievanceActionRequest = {
  action: 'generate_grievance'
}

/** WorkspaceActionResponse focused on grievance generation. */
export type GenerateGrievanceResponse = {
  case_uuid: string
  action: 'generate_grievance' | string
  status: string
  message: string
  steward_action_label?: string | null
  available_actions?: WorkspaceActionAvailability[]
  missing_prerequisites?: WorkspaceActionPrerequisite[]
  grievance_draft_created?: boolean
  grievance_generation?: GrievanceGenerationResult | null
  official_artifact_created?: boolean
  prior_report_version_number?: number | null
  current_report_version_number?: number | null
  [key: string]: unknown
}

/** Client-held temporary editable draft (not a server resource). */
export type TemporaryGrievanceDraft = {
  template_id: SupportedGrievanceTemplateId
  step_type: GrievanceStepType | null
  draft_status: DraftStatus | null
  field_values: Record<string, string>
  /** Field IDs steward changed after Generate. */
  steward_override_field_ids: string[]
  /** Snapshot of generated values at Generate time (for provenance labels). */
  generated_field_values: Record<string, string>
  message?: string | null
}

/** POST /cases/{uuid}/grievances/save-and-print */
export type SaveAndPrintGrievanceRequest = {
  template_id: string
  template_version?: string | null
  grievance_step?: string | null
  field_values?: Record<string, unknown>
  steward_override_field_ids?: string[]
  missing_required_field_ids?: string[]
  validation_status?: string | null
  draft_status?: string | null
  content_snapshot?: Record<string, unknown> | null
  working_draft_uuid?: string | null
  title?: string | null
  saved_by?: string | null
  idempotency_key?: string | null
  prepare_pdf?: boolean
}

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
