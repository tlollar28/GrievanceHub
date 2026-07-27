/**
 * Hand-mirrored from app/schemas/case_asset_schema.py and
 * CASE_ASSET_MAX_UPLOAD_BYTES in app/config.py.
 * OpenAPI asset response schemas are empty — Pydantic models are source of truth.
 */

export type CaseAssetCategory =
  | 'uploaded_document'
  | 'generated_report'
  | 'generated_grievance'
  | 'future_export'
  | 'future_attachment'

export type CaseAssetStatus = 'active' | 'superseded' | 'archived'

export type CaseAssetSource =
  | 'manual_ui'
  | 'api'
  | 'system'
  | 'update_analysis'
  | 'generate_grievance'
  | 'export'
  | string

/** Backend CASE_ASSET_MAX_UPLOAD_BYTES = 25 * 1024 * 1024 */
export const CASE_ASSET_MAX_UPLOAD_BYTES = 25 * 1024 * 1024

/** Only uploaded_document is executable for steward uploads. */
export const EXECUTABLE_UPLOAD_CATEGORY: CaseAssetCategory = 'uploaded_document'

/**
 * Full metadata shape returned by the backend. UI must not render storage
 * path fields (`stored_path`, `stored_filename`).
 */
export type CaseAssetMetadata = {
  asset_uuid: string
  case_uuid: string
  asset_category: CaseAssetCategory | string
  original_filename?: string | null
  stored_filename?: string | null
  stored_path?: string | null
  mime_type?: string | null
  file_size?: number | null
  sha256?: string | null
  uploaded_by?: string | null
  source?: CaseAssetSource
  version_number?: number
  parent_asset_uuid?: string | null
  report_version_id?: number | null
  report_version_number?: number | null
  draft_record_uuid?: string | null
  status?: CaseAssetStatus | string
  asset_metadata?: Record<string, unknown> | null
  created_at?: string | null
  updated_at?: string | null
}

export type CaseAssetListResponse = {
  case_uuid: string
  count: number
  assets: CaseAssetMetadata[]
}

export type CaseAssetUploadResponse = {
  case_uuid: string
  asset: CaseAssetMetadata
  message?: string
}

export type ListCaseAssetsParams = {
  category?: CaseAssetCategory
}

export type UploadCaseAssetFields = {
  file: File
  category?: CaseAssetCategory
  uploaded_by?: string | null
  source?: string
}
