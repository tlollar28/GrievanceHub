import { apiBinaryRequest, apiRequest } from './client'
import type {
  BinaryExportResult,
  CaseSavedArtifactDetail,
  CaseSavedArtifactListResponse,
  GenerateGrievanceActionRequest,
  GenerateGrievanceResponse,
  GrievanceGenerationResult,
  SaveAndPrintGrievanceRequest,
  SaveAndPrintResponse,
} from './types/grievances'

const SUPPORTED_TEMPLATE_IDS = new Set([
  'official_grievance_worksheet_step_1',
  'official_standard_grievance_form_step_2',
])

/**
 * POST /cases/{case_uuid}/actions
 * Explicit Generate Grievance — temporary editable draft only.
 */
export function generateGrievance(
  caseUuid: string,
  signal?: AbortSignal,
): Promise<GenerateGrievanceResponse> {
  const body: GenerateGrievanceActionRequest = {
    action: 'generate_grievance',
  }
  return apiRequest<GenerateGrievanceResponse>(`/cases/${caseUuid}/actions`, {
    method: 'POST',
    body,
    signal,
  })
}

/**
 * POST /cases/{case_uuid}/grievances/save-and-print
 * Save (prepare_pdf:false) or Save and Print (prepare_pdf:true).
 */
export function saveAndPrintGrievance(
  caseUuid: string,
  body: SaveAndPrintGrievanceRequest,
  signal?: AbortSignal,
): Promise<SaveAndPrintResponse> {
  return apiRequest<SaveAndPrintResponse>(
    `/cases/${caseUuid}/grievances/save-and-print`,
    {
      method: 'POST',
      body,
      signal,
    },
  )
}

/**
 * GET /cases/{case_uuid}/artifacts?artifact_type=grievance_form
 */
export function listGrievanceArtifacts(
  caseUuid: string,
  signal?: AbortSignal,
): Promise<CaseSavedArtifactListResponse> {
  return apiRequest<CaseSavedArtifactListResponse>(
    `/cases/${caseUuid}/artifacts?artifact_type=grievance_form`,
    { signal },
  )
}

/**
 * GET /cases/{case_uuid}/artifacts/{artifact_uuid}
 */
export function getGrievanceArtifact(
  caseUuid: string,
  artifactUuid: string,
  signal?: AbortSignal,
): Promise<CaseSavedArtifactDetail> {
  return apiRequest<CaseSavedArtifactDetail>(
    `/cases/${caseUuid}/artifacts/${artifactUuid}`,
    { signal },
  )
}

/**
 * GET /cases/{case_uuid}/artifacts/{artifact_uuid}/pdf
 */
export function fetchGrievanceArtifactPdf(
  caseUuid: string,
  artifactUuid: string,
  signal?: AbortSignal,
): Promise<BinaryExportResult> {
  return apiBinaryRequest(
    `/cases/${caseUuid}/artifacts/${artifactUuid}/pdf`,
    {
      accept: 'application/pdf',
      signal,
    },
  )
}

/** Extract generation result; null when prerequisites failed or no draft. */
export function extractGrievanceGeneration(
  response: GenerateGrievanceResponse,
): GrievanceGenerationResult | null {
  return response.grievance_generation ?? null
}

/**
 * True when generate completed with a supported Step 1 / Step 2 template
 * and a field_values map suitable for the editable draft UI.
 */
export function isSupportedGrievanceDraft(
  generation: GrievanceGenerationResult | null | undefined,
): boolean {
  if (!generation || generation.draft_created === false) return false
  if (
    !generation.template_id ||
    !SUPPORTED_TEMPLATE_IDS.has(generation.template_id)
  ) {
    return false
  }
  if (!generation.field_values || typeof generation.field_values !== 'object') {
    return false
  }
  return true
}

/** Normalize flat field_values to string map for the editor. */
export function flattenFieldValues(
  fieldValues: Record<string, unknown> | null | undefined,
): Record<string, string> {
  const out: Record<string, string> = {}
  if (!fieldValues) return out
  for (const [key, value] of Object.entries(fieldValues)) {
    if (value == null) {
      out[key] = ''
    } else if (typeof value === 'string') {
      out[key] = value
    } else if (typeof value === 'number' || typeof value === 'boolean') {
      out[key] = String(value)
    } else if (Array.isArray(value)) {
      out[key] = value.map((item) => String(item)).join(', ')
    } else {
      // Do not invent structured objects as form text.
      out[key] = ''
    }
  }
  return out
}
