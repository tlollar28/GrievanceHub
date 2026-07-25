import { apiBinaryRequest, apiRequest } from './client'
import type {
  AnalysisVersionDetail,
  AnalysisVersionListResponse,
  BinaryExportResult,
  GenerateAnalysisRequest,
  GenerateAnalysisResponse,
  SaveAndPrintReportRequest,
  SaveAndPrintResponse,
} from './types/reports'

/**
 * POST /cases/{case_uuid}/reports/generate
 * Temporary read-only preview only — no CaseReportVersion or artifact.
 */
export function generateAnalysisReport(
  caseUuid: string,
  body: GenerateAnalysisRequest = {},
  signal?: AbortSignal,
): Promise<GenerateAnalysisResponse> {
  return apiRequest<GenerateAnalysisResponse>(
    `/cases/${caseUuid}/reports/generate`,
    {
      method: 'POST',
      body: {
        limit_per_source: body.limit_per_source ?? 8,
      },
      signal,
    },
  )
}

/**
 * POST /cases/{case_uuid}/reports/save-and-print
 * Single persistence endpoint for Save (prepare_pdf:false) and
 * Save and Print (prepare_pdf:true).
 */
export function saveAndPrintAnalysisReport(
  caseUuid: string,
  body: SaveAndPrintReportRequest,
  signal?: AbortSignal,
): Promise<SaveAndPrintResponse> {
  return apiRequest<SaveAndPrintResponse>(
    `/cases/${caseUuid}/reports/save-and-print`,
    {
      method: 'POST',
      body,
      signal,
    },
  )
}

/**
 * GET /cases/{case_uuid}/versions
 */
export function listAnalysisVersions(
  caseUuid: string,
  signal?: AbortSignal,
): Promise<AnalysisVersionListResponse> {
  return apiRequest<AnalysisVersionListResponse>(
    `/cases/${caseUuid}/versions`,
    { signal },
  )
}

/**
 * GET /cases/{case_uuid}/versions/{version_number}
 */
export function getAnalysisVersion(
  caseUuid: string,
  versionNumber: number,
  signal?: AbortSignal,
): Promise<AnalysisVersionDetail> {
  return apiRequest<AnalysisVersionDetail>(
    `/cases/${caseUuid}/versions/${versionNumber}`,
    { signal },
  )
}

export type VersionExportKind = 'preview' | 'html' | 'pdf'

export type FetchVersionExportOptions = {
  workingDraft?: boolean
  signal?: AbortSignal
}

/**
 * Version-scoped HTML/PDF export.
 * Official PDF (workingDraft=false) requires prior Save and Print → 409 otherwise.
 */
export function fetchVersionExport(
  caseUuid: string,
  versionNumber: number,
  kind: VersionExportKind,
  options: FetchVersionExportOptions = {},
): Promise<BinaryExportResult> {
  let path = `/cases/${caseUuid}/versions/${versionNumber}/export/${kind}`
  if (kind === 'pdf' && options.workingDraft) {
    path += '?working_draft=true'
  }
  const accept =
    kind === 'pdf' ? 'application/pdf' : 'text/html, application/xhtml+xml'
  return apiBinaryRequest(path, {
    accept,
    signal: options.signal,
  })
}

/**
 * Official artifact PDF from Save and Print export_path /
 * GET /cases/{uuid}/artifacts/{artifact_uuid}/pdf
 */
export function fetchArtifactPdf(
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

/** Prefer preview from generate response; fall back to analysis_preview. */
export function extractAnalysisPreview(
  response: GenerateAnalysisResponse,
): GenerateAnalysisResponse['preview'] {
  return response.preview ?? response.analysis_preview ?? null
}
