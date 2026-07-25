/**
 * Hand-mirrored from app/schemas/case_saved_artifact_schema.py,
 * case_workspace_action_schema.py, report_schema.py, and
 * CaseService / cases.py version serialization.
 * OpenAPI report response schemas are incomplete — Pydantic is source of truth.
 */

export type GenerateAnalysisRequest = {
  limit_per_source?: number
}

export type WorkspaceActionPrerequisite = {
  code: string
  message: string
}

export type WorkspaceActionAvailability = {
  action: string
  available: boolean
  steward_visible?: boolean
  reason?: string | null
  missing_prerequisites?: WorkspaceActionPrerequisite[]
  [key: string]: unknown
}

/** Temporary preview payload returned by POST .../reports/generate. */
export type AnalysisPreviewPayload = {
  temporary?: boolean
  persisted?: boolean
  review_mode?: string
  editable?: boolean
  suggested_version_number_if_saved?: number | null
  report_data?: GrievanceHubReportData | null
  ranked_authorities?: unknown
  issue_analysis?: unknown
  evidence_items?: unknown
  retrieval_gaps?: Record<string, unknown> | null
  source_coverage_audit?: unknown
  report_summary?: unknown
  [key: string]: unknown
}

export type ReportCitation = {
  document_name?: string
  document_type?: string
  page?: number | null
  chunk?: number | null
}

export type AuthorityReportItem = {
  article_or_section?: string
  issue?: string
  role?: string
  role_title?: string
  why_relevant?: string
  direct_quote?: string
  relevance_score?: number | null
  keyword_overlap?: number | null
  citation?: ReportCitation
  provenance?: Record<string, unknown> | null
  [key: string]: unknown
}

export type EvidenceItem = {
  article_or_section?: string
  document_name?: string
  document_type?: string
  page?: number | null
  chunk?: number | null
  direct_quote?: string
  what_it_supports?: string
  how_to_use?: string
  provenance?: Record<string, unknown> | null
  [key: string]: unknown
}

export type QuickAssessment = {
  summary?: string
  grievability?: string
  confidence?: string
  why?: string
  cited_authorities?: string[]
  provenance?: Record<string, unknown> | null
}

export type RecommendedRemedy = {
  statements?: string[]
  grounding_authorities?: string[]
  insufficient_notice?: string | null
  provenance?: Record<string, unknown> | null
}

export type DetailedAnalysis = {
  grievance_framework?: string
  evidence_to_gather?: string[]
  strategic_tips?: Array<{ title?: string; text?: string }>
  provenance?: Record<string, unknown> | null
}

export type Limitations = {
  missing_facts?: string[]
  retrieval_gaps?: Record<string, unknown>
  known_facts?: string[]
  caveats?: string[]
  provenance?: Record<string, unknown> | null
}

export type CitationValidation = {
  status?: string
  evidence_items_checked?: number
  direct_quotes_found?: number
  notes?: string[]
}

export type CaseInformation = {
  case_id?: string | null
  case_title?: string | null
  user_name?: string | null
  local_number?: string | null
}

/** Structured report_data from AnalysisService / GrievanceHubReport. */
export type GrievanceHubReportData = {
  report_title?: string
  brand?: string
  generated_at?: string
  case_information?: CaseInformation
  research_draft_notice?: string
  your_question?: string
  quick_assessment?: QuickAssessment
  secondary_issues?: string[]
  key_contract_violations?: AuthorityReportItem[]
  recommended_remedy?: RecommendedRemedy
  detailed_analysis?: DetailedAnalysis
  matching_grievance_templates?: unknown[]
  matching_grievance_templates_notice?: string
  supporting_evidence?: EvidenceItem[]
  union_supporting_authority?: AuthorityReportItem[]
  procedural_requirements?: AuthorityReportItem[]
  information_rights?: AuthorityReportItem[]
  timeline_requirements?: AuthorityReportItem[]
  remedy_authority?: AuthorityReportItem[]
  management_limiting_authority?: AuthorityReportItem[]
  background_authority?: AuthorityReportItem[]
  limitations?: Limitations
  source_references?: {
    found?: Array<{
      source_type?: string
      document_names?: string[]
      authority_count?: number
    }>
    not_found?: Array<{
      source_type?: string | null
      issue?: string
      reason?: string
    }>
  }
  source_summary?: Record<string, unknown>
  citation_validation?: CitationValidation | null
  issue_analysis?: Record<string, unknown> | null
  ranked_authorities?: unknown
  [key: string]: unknown
}

export type GenerateAnalysisResponse = {
  case_uuid: string
  action?: string
  status?: string
  message?: string
  review_mode?: string
  editable?: boolean
  persisted?: boolean
  report_version?: number | null
  preview?: AnalysisPreviewPayload | null
  analysis_preview?: AnalysisPreviewPayload | null
  analysis_preview_ready?: boolean
  analysis_editable?: boolean
  official_artifact_created?: boolean
  missing_prerequisites?: WorkspaceActionPrerequisite[]
  available_actions?: WorkspaceActionAvailability[]
  prior_report_version_number?: number | null
  current_report_version_number?: number | null
  [key: string]: unknown
}

export type SaveAndPrintReportRequest = {
  report_version_number?: number | null
  preview?: AnalysisPreviewPayload | Record<string, unknown> | null
  title?: string | null
  saved_by?: string | null
  grievance_step?: string | null
  idempotency_key?: string | null
  prepare_pdf?: boolean
}

export type PdfStatus = 'pending' | 'ready' | 'failed' | string

export type CaseSavedArtifactSummary = {
  artifact_uuid: string
  case_uuid: string
  artifact_type: 'analysis_report' | 'grievance_form' | string
  title: string
  version_number: number
  version_label: string
  grievance_step?: string | null
  template_id?: string | null
  template_version?: string | null
  printed?: boolean
  pdf_status?: PdfStatus
  pdf_asset_uuid?: string | null
  is_latest_official?: boolean
  saved_by?: string | null
  saved_at: string
  source_report_version_number?: number | null
  source_draft_record_uuid?: string | null
  key_summary?: Record<string, unknown> | null
  retrieval?: Record<string, string> | null
}

export type SaveAndPrintStatus =
  | 'saved'
  | 'saved_pdf_failed'
  | 'idempotent_replay'

export type SaveAndPrintResponse = {
  case_uuid: string
  status: SaveAndPrintStatus
  message: string
  artifact: CaseSavedArtifactSummary
  print_ready?: boolean
  pdf_error?: string | null
  export_path?: string | null
}

/** List item from GET /cases/{uuid}/versions (include_report=false). */
export type AnalysisVersionSummary = {
  id: number
  version_number: number
  trigger_message_id?: number | null
  created_at?: string | null
  retrieval_gaps?: Record<string, unknown> | null
  source_coverage_audit?: unknown
  report_summary?: unknown
}

export type AnalysisVersionListResponse = {
  case_uuid: string
  count: number
  versions: AnalysisVersionSummary[]
}

/** Detail from GET /cases/{uuid}/versions/{n} (include_report=true). */
export type AnalysisVersionDetail = AnalysisVersionSummary & {
  report_data?: GrievanceHubReportData | null
  ranked_authorities?: unknown
  issue_analysis?: unknown
  evidence_items?: unknown
}

export type BinaryExportResult = {
  blob: Blob
  contentType: string
  filename: string | null
  printMode: string | null
}
