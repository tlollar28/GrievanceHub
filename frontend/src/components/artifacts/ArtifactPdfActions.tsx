import { useEffect, useId, useRef, useState } from 'react'
import { fetchCaseArtifactPdf } from '../../api/artifacts'
import { ApiError } from '../../api/client'
import {
  artifactTypeLabel,
  pdfStatusLabel,
} from '../../features/artifacts/artifactLibraryFilters'
import styles from './ArtifactsPanel.module.css'

type Props = {
  caseUuid: string
  artifactUuid: string
  artifactType?: string | null
  title?: string | null
  pdfStatus?: string | null
}

function revokeUrl(url: string | null) {
  if (url) URL.revokeObjectURL(url)
}

export function ArtifactPdfActions({
  caseUuid,
  artifactUuid,
  artifactType,
  title,
  pdfStatus,
}: Props) {
  const headingId = useId()
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [previewUrl, setPreviewUrl] = useState<string | null>(null)
  const activeUrlRef = useRef<string | null>(null)

  useEffect(() => {
    return () => {
      revokeUrl(activeUrlRef.current)
      activeUrlRef.current = null
    }
  }, [])

  useEffect(() => {
    setError(null)
    setPreviewUrl((current) => {
      revokeUrl(current)
      return null
    })
    activeUrlRef.current = null
  }, [caseUuid, artifactUuid])

  async function openPdf() {
    setBusy(true)
    setError(null)
    try {
      const result = await fetchCaseArtifactPdf(caseUuid, artifactUuid)
      const url = URL.createObjectURL(result.blob)
      revokeUrl(activeUrlRef.current)
      activeUrlRef.current = url
      setPreviewUrl(url)
    } catch (err) {
      if (err instanceof ApiError && err.status === 404) {
        setError(
          pdfStatus === 'failed'
            ? 'PDF preparation failed for this saved artifact. The official record remains saved.'
            : 'Official PDF is not available for this artifact yet.',
        )
      } else if (err instanceof ApiError) {
        setError(err.message)
      } else {
        setError('Unable to open the official artifact PDF.')
      }
    } finally {
      setBusy(false)
    }
  }

  const typeLabel = artifactTypeLabel(artifactType)
  const iframeTitle =
    title?.trim() ||
    `${typeLabel} PDF`

  return (
    <section className={styles.section} aria-labelledby={headingId}>
      <h3 id={headingId} className={styles.sectionHeading}>
        Official PDF
      </h3>
      <p className={styles.statusText} role="status">
        {pdfStatusLabel(pdfStatus)}. Opening PDF does not regenerate or modify
        this artifact.
      </p>
      <div className={styles.exportRow}>
        <button
          type="button"
          className={styles.button}
          disabled={busy || pdfStatus === 'pending'}
          aria-busy={busy}
          onClick={() => {
            void openPdf()
          }}
        >
          {busy ? 'Opening PDF…' : 'Preview PDF'}
        </button>
        {previewUrl ? (
          <a
            className={styles.secondaryButton}
            href={previewUrl}
            download={`${artifactUuid}.pdf`}
          >
            Download PDF
          </a>
        ) : null}
      </div>
      {pdfStatus === 'failed' && !error ? (
        <div className={styles.warningBox} role="status">
          PDF status is failed. You may still retry the preview request.
        </div>
      ) : null}
      {error ? (
        <div className={styles.errorBox} role="alert">
          {error}
        </div>
      ) : null}
      {previewUrl ? (
        <div>
          <p className={styles.statusText} role="status">
            Showing official PDF for {typeLabel}.
          </p>
          <iframe
            className={styles.previewFrame}
            title={iframeTitle}
            src={previewUrl}
          />
          <div className={styles.exportRow}>
            <a
              className={styles.secondaryButton}
              href={previewUrl}
              target="_blank"
              rel="noreferrer"
            >
              Open in new tab
            </a>
            <button
              type="button"
              className={styles.secondaryButton}
              onClick={() => {
                revokeUrl(previewUrl)
                if (activeUrlRef.current === previewUrl) {
                  activeUrlRef.current = null
                }
                setPreviewUrl(null)
              }}
            >
              Close preview
            </button>
          </div>
        </div>
      ) : null}
    </section>
  )
}
