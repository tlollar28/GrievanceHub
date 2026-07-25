import { apiMultipartRequest, apiRequest } from './client'
import type {
  CaseAssetListResponse,
  CaseAssetMetadata,
  CaseAssetUploadResponse,
  ListCaseAssetsParams,
  UploadCaseAssetFields,
} from './types/assets'
import { EXECUTABLE_UPLOAD_CATEGORY } from './types/assets'

function assetsPath(caseUuid: string, query?: ListCaseAssetsParams): string {
  const base = `/cases/${caseUuid}/assets`
  if (!query?.category) {
    return base
  }
  const params = new URLSearchParams({ category: query.category })
  return `${base}?${params.toString()}`
}

/**
 * GET /cases/{case_uuid}/assets
 */
export function listCaseAssets(
  caseUuid: string,
  params: ListCaseAssetsParams = {},
  signal?: AbortSignal,
): Promise<CaseAssetListResponse> {
  return apiRequest<CaseAssetListResponse>(assetsPath(caseUuid, params), {
    signal,
  })
}

/**
 * GET /cases/{case_uuid}/assets/{asset_uuid}
 * Metadata only — no file body.
 */
export function getCaseAsset(
  caseUuid: string,
  assetUuid: string,
  signal?: AbortSignal,
): Promise<CaseAssetMetadata> {
  return apiRequest<CaseAssetMetadata>(
    `/cases/${caseUuid}/assets/${assetUuid}`,
    { signal },
  )
}

/**
 * POST /cases/{case_uuid}/assets (multipart).
 * Does not set Content-Type; browser supplies the boundary.
 */
export function uploadCaseAsset(
  caseUuid: string,
  fields: UploadCaseAssetFields,
  signal?: AbortSignal,
): Promise<CaseAssetUploadResponse> {
  const formData = new FormData()
  formData.append('file', fields.file, fields.file.name)
  formData.append('category', fields.category ?? EXECUTABLE_UPLOAD_CATEGORY)
  formData.append('source', fields.source ?? 'manual_ui')
  if (fields.uploaded_by != null && fields.uploaded_by.trim().length > 0) {
    formData.append('uploaded_by', fields.uploaded_by.trim())
  }

  return apiMultipartRequest<CaseAssetUploadResponse>(
    `/cases/${caseUuid}/assets`,
    {
      method: 'POST',
      formData,
      signal,
    },
  )
}
