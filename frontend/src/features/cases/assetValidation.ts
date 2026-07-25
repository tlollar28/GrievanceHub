import {
  CASE_ASSET_MAX_UPLOAD_BYTES,
  EXECUTABLE_UPLOAD_CATEGORY,
} from '../../api/types/assets'

export type AssetClientValidationError = {
  code: 'no_file' | 'empty_file' | 'file_too_large'
  message: string
}

export function formatFileSize(bytes: number | null | undefined): string {
  if (bytes == null || Number.isNaN(bytes) || bytes < 0) {
    return '—'
  }
  if (bytes < 1024) {
    return `${bytes} B`
  }
  if (bytes < 1024 * 1024) {
    return `${(bytes / 1024).toFixed(1)} KB`
  }
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

/**
 * Client-side checks aligned with CaseAssetService validation.
 * Server validation remains authoritative. No MIME whitelist — backend
 * accepts any non-empty file under the size limit.
 */
export function validateUploadFile(
  file: File | null | undefined,
): AssetClientValidationError | null {
  if (!file) {
    return {
      code: 'no_file',
      message: 'Choose a file before uploading.',
    }
  }
  if (file.size <= 0) {
    return {
      code: 'empty_file',
      message: 'Uploaded file is empty.',
    }
  }
  if (file.size > CASE_ASSET_MAX_UPLOAD_BYTES) {
    return {
      code: 'file_too_large',
      message: `File exceeds maximum size of ${formatFileSize(CASE_ASSET_MAX_UPLOAD_BYTES)}.`,
    }
  }
  return null
}

export function uploadGuidanceText(): string {
  return [
    `Category: ${EXECUTABLE_UPLOAD_CATEGORY} (only executable upload type).`,
    `Maximum size: ${formatFileSize(CASE_ASSET_MAX_UPLOAD_BYTES)}.`,
    'Empty files are rejected.',
    'The backend does not restrict MIME type for uploads.',
    'Uploaded evidence is attached as case context. It is not full-text searched like the indexed authority corpus.',
  ].join(' ')
}
