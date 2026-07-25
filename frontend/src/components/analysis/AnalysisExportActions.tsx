import { useEffect, useId, useRef, useState } from 'react'
import { ApiError } from '../../api/client'
import { fetchArtifactPdf, fetchVersionExport } from '../../api/reports'
import styles from './AnalysisPanel.module.css'

type Props = {
  caseUuid: string
  versionNumber: number
  artifactUuid?: string | null
  exportPath?: string | null
}

type PreviewState = {
  url: string
  label: string
  kind: 'html' | 'pdf'
}

function revokeUrl(url: string | null) {
  if (url) {
    URL.revokeObjectURL(url)
  }
}

export function AnalysisExportActions({
  caseUuid,
  versionNumber,
  artifactUuid,
  exportPath,
}: Props) {
  const headingId = useId()
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [preview, setPreview] = useState<PreviewState | null>(null)
  const activeUrlRef = useRef<string | null>(null)

  useEffect(() => {
    return () => {
      revokeUrl(activeUrlRef.current)
      activeUrlRef.current = null
    }
  }, [])

  useEffect(() => {
    setError(null)
    setPreview((current) => {
      if (current) {
        revokeUrl(current.url)
      }
      return null
    })
    activeUrlRef.current = null
  }, [caseUuid, versionNumber])

  async function openBinary(
    label: string,
    kind: 'html' | 'pdf',
    loader: () => Promise<{ blob: Blob; printMode: string | null }>,
  ) {
    setBusy(true)
    setError(null)
    try {
      const result = await loader()
      const url = URL.createObjectURL(result.blob)
      revokeUrl(activeUrlRef.current)
      activeUrlRef.current = url
      const modeNote =
        result.printMode === 'working_draft_preview'
          ? 'Working-draft preview (not official)'
          : result.printMode === 'official_saved_artifact'
            ? 'Official saved artifact'
            : label
      setPreview({ url, label: modeNote, kind })
    } catch (err) {
      if (err instanceof ApiError && err.status === 409) {
        setError(
          'Official PDF requires Save and Print first. Use working-draft PDF only for non-official preview, or open the official artifact PDF after Save and Print.',
        )
      } else if (err instanceof ApiError) {
        setError(err.message)
      } else {
        setError('Unable to open export.')
      }
    } finally {
      setBusy(false)
    }
  }

  return (
    <section className={styles.section} aria-labelledby={headingId}>
      <h3 id={headingId} className={styles.sectionHeading}>
        Export and print
      </h3>
      <p className={styles.exportHint}>
        Official PDF requires a prior Save and Print. Working-draft PDF is a
        non-official preview only.
      </p>
      <div className={styles.exportRow}>
        <button
          type="button"
          className={styles.exportButton}
          disabled={busy}
          aria-busy={busy}
          onClick={() => {
            void openBinary('HTML preview', 'html', () =>
              fetchVersionExport(caseUuid, versionNumber, 'preview'),
            )
          }}
        >
          Open HTML preview
        </button>
        <button
          type="button"
          className={styles.exportButton}
          disabled={busy}
          aria-busy={busy}
          onClick={() => {
            void openBinary('Working-draft PDF', 'pdf', () =>
              fetchVersionExport(caseUuid, versionNumber, 'pdf', {
                workingDraft: true,
              }),
            )
          }}
        >
          Working-draft PDF
        </button>
        <button
          type="button"
          className={styles.exportButton}
          disabled={busy}
          aria-busy={busy}
          onClick={() => {
            void openBinary('Official PDF', 'pdf', () =>
              fetchVersionExport(caseUuid, versionNumber, 'pdf', {
                workingDraft: false,
              }),
            )
          }}
        >
          Official PDF
        </button>
        {artifactUuid ? (
          <button
            type="button"
            className={styles.exportButton}
            disabled={busy}
            aria-busy={busy}
            onClick={() => {
              void openBinary('Official artifact PDF', 'pdf', () =>
                fetchArtifactPdf(caseUuid, artifactUuid),
              )
            }}
          >
            Artifact PDF
          </button>
        ) : null}
        {exportPath && !artifactUuid ? (
          <p className={styles.exportHint}>
            Server export path available after Save and Print (not shown as a
            raw storage path).
          </p>
        ) : null}
      </div>
      {error ? (
        <div className={styles.errorBox} role="alert">
          {error}
        </div>
      ) : null}
      {preview ? (
        <div>
          <p className={styles.statusText} role="status">
            Showing: {preview.label}
          </p>
          {preview.kind === 'html' ? (
            <iframe
              className={styles.previewFrame}
              title={`Analysis HTML preview — ${preview.label}`}
              src={preview.url}
            />
          ) : (
            <iframe
              className={styles.previewFrame}
              title={`Analysis PDF preview — ${preview.label}`}
              src={preview.url}
            />
          )}
          <div className={styles.exportRow}>
            <a
              className={styles.exportButton}
              href={preview.url}
              target="_blank"
              rel="noreferrer"
            >
              Open in new tab
            </a>
            <button
              type="button"
              className={styles.secondaryButton}
              onClick={() => {
                revokeUrl(preview.url)
                if (activeUrlRef.current === preview.url) {
                  activeUrlRef.current = null
                }
                setPreview(null)
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
