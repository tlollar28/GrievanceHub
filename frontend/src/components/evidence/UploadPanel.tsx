import { useId, useRef, useState } from 'react'
import { ApiError } from '../../api/client'
import {
  EXECUTABLE_UPLOAD_CATEGORY,
  type CaseAssetMetadata,
} from '../../api/types/assets'
import {
  formatFileSize,
  uploadGuidanceText,
  validateUploadFile,
} from '../../features/cases/assetValidation'
import { useUploadAssetMutation } from '../../features/cases/useUploadAssetMutation'
import styles from './EvidencePanel.module.css'

type Props = {
  caseUuid: string
  uploadedBy?: string | null
  disabled?: boolean
  onUploaded?: (asset: CaseAssetMetadata) => void
}

export function UploadPanel({
  caseUuid,
  uploadedBy,
  disabled = false,
  onUploaded,
}: Props) {
  const headingId = useId()
  const inputId = useId()
  const guidanceId = useId()
  const inputRef = useRef<HTMLInputElement>(null)
  const abortRef = useRef<AbortController | null>(null)
  const caseUuidRef = useRef(caseUuid)
  const mutation = useUploadAssetMutation()
  const [file, setFile] = useState<File | null>(null)
  const [localError, setLocalError] = useState<string | null>(null)
  const [successMessage, setSuccessMessage] = useState<string | null>(null)

  caseUuidRef.current = caseUuid

  function resetForm() {
    setFile(null)
    setLocalError(null)
    if (inputRef.current) {
      inputRef.current.value = ''
    }
    mutation.reset()
  }

  async function handleSubmit() {
    if (disabled || mutation.isPending) {
      return
    }
    const validation = validateUploadFile(file)
    if (validation) {
      setLocalError(validation.message)
      setSuccessMessage(null)
      return
    }
    if (!file) {
      return
    }

    setLocalError(null)
    setSuccessMessage(null)
    abortRef.current?.abort()
    const controller = new AbortController()
    abortRef.current = controller
    const requestCaseUuid = caseUuid

    try {
      const result = await mutation.mutateAsync({
        caseUuid: requestCaseUuid,
        fields: {
          file,
          category: EXECUTABLE_UPLOAD_CATEGORY,
          source: 'manual_ui',
          uploaded_by: uploadedBy ?? null,
        },
        signal: controller.signal,
      })

      if (caseUuidRef.current !== requestCaseUuid) {
        return
      }

      const name =
        result.asset.original_filename?.trim() || result.asset.asset_uuid
      setSuccessMessage(`Uploaded ${name}.`)
      resetForm()
      onUploaded?.(result.asset)
    } catch (error) {
      if (error instanceof DOMException && error.name === 'AbortError') {
        return
      }
      if (caseUuidRef.current !== requestCaseUuid) {
        return
      }
      setLocalError(
        error instanceof ApiError
          ? error.message
          : 'Unable to upload the file.',
      )
    }
  }

  const busy = mutation.isPending

  return (
    <section
      className={styles.section}
      aria-labelledby={headingId}
      aria-busy={busy || undefined}
    >
      <h3 id={headingId} className={styles.sectionHeading}>
        Upload evidence
      </h3>
      <p id={guidanceId} className={styles.guidance}>
        {uploadGuidanceText()}
      </p>

      <form
        className={styles.form}
        onSubmit={(event) => {
          event.preventDefault()
          void handleSubmit()
        }}
      >
        <label className={styles.label} htmlFor={inputId}>
          Evidence file
        </label>
        <input
          ref={inputRef}
          id={inputId}
          className={styles.fileInput}
          type="file"
          name="file"
          disabled={disabled || busy}
          aria-describedby={guidanceId}
          onChange={(event) => {
            const next = event.target.files?.[0] ?? null
            setFile(next)
            setLocalError(null)
            setSuccessMessage(null)
          }}
        />
        <p className={styles.selectedFile} role="status">
          {file
            ? `Selected: ${file.name} (${formatFileSize(file.size)})`
            : 'No file selected.'}
        </p>

        <div className={styles.formActions}>
          <button
            type="submit"
            className={styles.primaryButton}
            disabled={disabled || busy || !file}
          >
            {busy ? 'Uploading…' : 'Upload'}
          </button>
          <button
            type="button"
            className={styles.secondaryButton}
            onClick={() => {
              abortRef.current?.abort()
              resetForm()
              setSuccessMessage(null)
            }}
          >
            Cancel
          </button>
        </div>
      </form>

      {localError ? (
        <div className={styles.errorBox} role="alert">
          <p>{localError}</p>
        </div>
      ) : null}

      {successMessage ? (
        <div className={styles.successBox} role="status">
          <p>{successMessage}</p>
        </div>
      ) : null}
    </section>
  )
}
