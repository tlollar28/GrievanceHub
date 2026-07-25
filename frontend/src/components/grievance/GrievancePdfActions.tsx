import { useEffect, useId, useRef, useState } from 'react'
import { ApiError } from '../../api/client'
import { fetchGrievanceArtifactPdf } from '../../api/grievances'
import {
  OFFICIAL_STEP_1_TEMPLATE_ID,
  OFFICIAL_STEP_2_TEMPLATE_ID,
  templateDisplayName,
} from '../../features/grievance/templateFields'
import styles from './GrievancePanel.module.css'

type Props = {
  caseUuid: string
  artifactUuid: string
  templateId?: string | null
  pdfStatus?: string | null
}

function revokeUrl(url: string | null) {
  if (url) URL.revokeObjectURL(url)
}

function officialPdfLabel(templateId: string | null | undefined): string {
  if (templateId === OFFICIAL_STEP_1_TEMPLATE_ID) {
    return 'Official Step 1 grievance worksheet PDF'
  }
  if (templateId === OFFICIAL_STEP_2_TEMPLATE_ID) {
    return 'Official Step 2 standard grievance form PDF'
  }
  return 'Official grievance PDF'
}

export function GrievancePdfActions({
  caseUuid,
  artifactUuid,
  templateId,
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
      const result = await fetchGrievanceArtifactPdf(caseUuid, artifactUuid)
      const url = URL.createObjectURL(result.blob)
      revokeUrl(activeUrlRef.current)
      activeUrlRef.current = url
      setPreviewUrl(url)
    } catch (err) {
      if (err instanceof ApiError && err.status === 409) {
        setError(
          'This official form PDF is not ready yet. Save and Print again, or wait until PDF status is ready.',
        )
      } else if (err instanceof ApiError && err.status === 404) {
        setError(
          pdfStatus === 'failed'
            ? 'PDF preparation failed for this saved grievance. The official artifact is still saved — retry Save and Print or contact support if the failure persists.'
            : 'Official form PDF is not available for this artifact yet.',
        )
      } else if (err instanceof ApiError) {
        setError(err.message)
      } else {
        setError('Unable to open the official grievance PDF.')
      }
    } finally {
      setBusy(false)
    }
  }

  const label = officialPdfLabel(templateId)
  const templateName = templateId
    ? templateDisplayName(templateId)
    : 'Official grievance form'

  return (
    <section className={styles.section} aria-labelledby={headingId}>
      <h3 id={headingId} className={styles.sectionHeading}>
        Official form PDF
      </h3>
      <p className={styles.exportHint}>
        {templateName}. PDF status: {pdfStatus ?? 'unknown'}. Official label
        applies only after a successful Save / Save and Print.
      </p>
      <div className={styles.exportRow}>
        <button
          type="button"
          className={styles.exportButton}
          disabled={busy || pdfStatus === 'pending'}
          aria-busy={busy}
          onClick={() => {
            void openPdf()
          }}
        >
          {busy ? 'Opening PDF…' : `Preview ${label}`}
        </button>
        {previewUrl ? (
          <a
            className={styles.exportButton}
            href={previewUrl}
            download={`${templateId ?? 'grievance'}.pdf`}
          >
            Download PDF
          </a>
        ) : null}
      </div>
      {error ? (
        <div className={styles.errorBox} role="alert">
          {error}
        </div>
      ) : null}
      {previewUrl ? (
        <div>
          <p className={styles.statusText} role="status">
            Showing: {label}
          </p>
          <iframe
            className={styles.previewFrame}
            title={label}
            src={previewUrl}
          />
          <div className={styles.exportRow}>
            <a
              className={styles.exportButton}
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
