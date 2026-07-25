import { useEffect, useId, useRef, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { ApiError } from '../../api/client'
import type {
  AnalysisPreviewPayload,
  SaveAndPrintStatus,
  WorkspaceActionAvailability,
} from '../../api/types/reports'
import { useAnalysisVersionsQuery } from '../../features/cases/useAnalysisVersionsQuery'
import { useGenerateAnalysisMutation } from '../../features/cases/useGenerateAnalysisMutation'
import { useSaveAnalysisMutation } from '../../features/cases/useSaveAnalysisMutation'
import { AnalysisPreview } from './AnalysisPreview'
import { AnalysisVersionDetail } from './AnalysisVersionDetail'
import { AnalysisVersionList } from './AnalysisVersionList'
import styles from './AnalysisPanel.module.css'

type Props = {
  caseUuid: string
  savedBy?: string | null
  readOnly?: boolean
  availableActions?: unknown[] | null
}

type SaveMode = 'save' | 'save_and_print'

type SaveFeedback = {
  status: SaveAndPrintStatus
  message: string
  kind: 'success' | 'warning'
}

function newIdempotencyKey(): string {
  if (typeof crypto !== 'undefined' && 'randomUUID' in crypto) {
    return crypto.randomUUID()
  }
  return `m5-${Date.now()}-${Math.random().toString(36).slice(2, 10)}`
}

function findGenerateAvailability(
  availableActions: unknown[] | null | undefined,
): WorkspaceActionAvailability | null {
  if (!availableActions) return null
  for (const item of availableActions) {
    if (!item || typeof item !== 'object') continue
    const row = item as WorkspaceActionAvailability
    if (row.action === 'generate_analysis_report') {
      return row
    }
  }
  return null
}

export function AnalysisPanel({
  caseUuid,
  savedBy,
  readOnly = false,
  availableActions,
}: Props) {
  const headingId = useId()
  const generateButtonRef = useRef<HTMLButtonElement | null>(null)
  const [searchParams, setSearchParams] = useSearchParams()
  const versionsQuery = useAnalysisVersionsQuery(caseUuid)
  const generateMutation = useGenerateAnalysisMutation()
  const saveMutation = useSaveAnalysisMutation()

  const [preview, setPreview] = useState<AnalysisPreviewPayload | null>(null)
  const [previewCaseUuid, setPreviewCaseUuid] = useState<string | null>(null)
  const [generateError, setGenerateError] = useState<string | null>(null)
  const [saveFeedback, setSaveFeedback] = useState<SaveFeedback | null>(null)
  const [saveError, setSaveError] = useState<string | null>(null)
  const [confirmCancel, setConfirmCancel] = useState(false)
  const [lastArtifactUuid, setLastArtifactUuid] = useState<string | null>(null)
  const idempotencyKeyRef = useRef<string | null>(null)
  const pendingSaveModeRef = useRef<SaveMode | null>(null)

  const selectedFromUrl = (() => {
    const raw = searchParams.get('version')
    if (!raw) return null
    const parsed = Number.parseInt(raw, 10)
    return Number.isFinite(parsed) && parsed > 0 ? parsed : null
  })()

  const versions = versionsQuery.data?.versions ?? []
  const selectedVersion =
    selectedFromUrl ??
    (versions.length > 0
      ? Math.max(...versions.map((v) => v.version_number))
      : null)

  const activePreview =
    preview && previewCaseUuid === caseUuid ? preview : null

  useEffect(() => {
    setPreview(null)
    setPreviewCaseUuid(null)
    setGenerateError(null)
    setSaveFeedback(null)
    setSaveError(null)
    setConfirmCancel(false)
    setLastArtifactUuid(null)
    idempotencyKeyRef.current = null
    pendingSaveModeRef.current = null
  }, [caseUuid])

  useEffect(() => {
    if (!activePreview) return
    const onBeforeUnload = (event: BeforeUnloadEvent) => {
      event.preventDefault()
      event.returnValue = ''
    }
    window.addEventListener('beforeunload', onBeforeUnload)
    return () => window.removeEventListener('beforeunload', onBeforeUnload)
  }, [activePreview])

  const generateAvailability = findGenerateAvailability(availableActions)
  const missingPrereqs =
    generateAvailability?.missing_prerequisites?.filter(
      (p) => p.message?.trim(),
    ) ?? []
  const generateBlocked =
    readOnly ||
    (generateAvailability != null && generateAvailability.available === false)

  const versionsError =
    versionsQuery.isError && !versionsQuery.data
      ? versionsQuery.error instanceof ApiError
        ? versionsQuery.error.message
        : 'Unable to load analysis versions.'
      : null

  function selectVersion(versionNumber: number) {
    const next = new URLSearchParams(searchParams)
    next.set('version', String(versionNumber))
    setSearchParams(next, { replace: true })
  }

  async function handleGenerate() {
    if (generateMutation.isPending || generateBlocked) return
    setGenerateError(null)
    setSaveFeedback(null)
    setSaveError(null)
    try {
      const result = await generateMutation.mutateAsync({ caseUuid })
      setPreview(result.preview)
      setPreviewCaseUuid(caseUuid)
      generateButtonRef.current?.focus()
    } catch (err) {
      setGenerateError(
        err instanceof ApiError
          ? err.message
          : 'Unable to generate analysis preview.',
      )
    }
  }

  function clearPreview() {
    setPreview(null)
    setPreviewCaseUuid(null)
    setConfirmCancel(false)
    idempotencyKeyRef.current = null
    pendingSaveModeRef.current = null
    generateButtonRef.current?.focus()
  }

  async function handleSave(mode: SaveMode) {
    if (!activePreview || saveMutation.isPending) return
    setSaveError(null)
    setSaveFeedback(null)

    if (
      !idempotencyKeyRef.current ||
      pendingSaveModeRef.current !== mode
    ) {
      idempotencyKeyRef.current = newIdempotencyKey()
      pendingSaveModeRef.current = mode
    }

    const preparePdf = mode === 'save_and_print'
    try {
      const result = await saveMutation.mutateAsync({
        caseUuid,
        body: {
          preview: activePreview,
          prepare_pdf: preparePdf,
          idempotency_key: idempotencyKeyRef.current,
          saved_by: savedBy ?? undefined,
        },
      })

      const kind: SaveFeedback['kind'] =
        result.status === 'saved_pdf_failed' ? 'warning' : 'success'
      setSaveFeedback({
        status: result.status,
        message: result.message,
        kind,
      })
      setLastArtifactUuid(result.artifact?.artifact_uuid ?? null)
      clearPreview()

      const version =
        result.artifact?.source_report_version_number ??
        result.artifact?.version_number
      if (typeof version === 'number') {
        selectVersion(version)
      }

      if (
        preparePdf &&
        result.print_ready &&
        result.artifact?.artifact_uuid
      ) {
        setLastArtifactUuid(result.artifact.artifact_uuid)
      }
    } catch (err) {
      setSaveError(
        err instanceof ApiError
          ? err.message
          : 'Unable to save the analysis report.',
      )
    }
  }

  const busy =
    generateMutation.isPending || saveMutation.isPending

  return (
    <div className={styles.panel}>
      <header className={styles.header}>
        <h2 id={headingId} className={styles.heading}>
          Analysis
        </h2>
        <p className={styles.subhead}>
          Generate a temporary read-only analysis preview, then Save or Save
          and Print to create an official version. Normal conversation does not
          create analysis reports.
        </p>
      </header>

      <div className={styles.toolbar}>
        <button
          ref={generateButtonRef}
          type="button"
          className={styles.primaryButton}
          disabled={busy || generateBlocked || Boolean(activePreview)}
          aria-busy={generateMutation.isPending}
          onClick={() => {
            void handleGenerate()
          }}
        >
          {generateMutation.isPending
            ? 'Generating analysis…'
            : 'Generate Analysis'}
        </button>
        {generateBlocked ? (
          <p className={styles.statusText} role="status">
            {readOnly
              ? 'Case is closed, settled, or archived. Reopen before generating analysis.'
              : generateAvailability?.reason ||
                'Generate Analysis prerequisites are not met.'}
          </p>
        ) : null}
      </div>

      {missingPrereqs.length > 0 ? (
        <ul className={styles.prereqList} aria-label="Missing prerequisites">
          {missingPrereqs.map((item) => (
            <li key={item.code}>{item.message}</li>
          ))}
        </ul>
      ) : null}

      {generateError ? (
        <div className={styles.errorBox} role="alert">
          <p>{generateError}</p>
          <button
            type="button"
            className={styles.retryButton}
            disabled={busy || generateBlocked}
            onClick={() => {
              void handleGenerate()
            }}
          >
            Retry
          </button>
        </div>
      ) : null}

      {saveFeedback ? (
        <div
          className={
            saveFeedback.kind === 'warning'
              ? styles.warningBox
              : styles.successBox
          }
          role="status"
        >
          <p>
            {saveFeedback.status === 'saved_pdf_failed'
              ? 'Analysis saved successfully, but PDF generation failed. You can retry export from the saved version.'
              : saveFeedback.status === 'idempotent_replay'
                ? 'Save replayed safely — no duplicate version was created.'
                : saveFeedback.message}
          </p>
          {saveFeedback.status === 'saved_pdf_failed' ? (
            <p>{saveFeedback.message}</p>
          ) : null}
        </div>
      ) : null}

      {saveError ? (
        <div className={styles.errorBox} role="alert">
          <p>{saveError}</p>
          {pendingSaveModeRef.current ? (
            <button
              type="button"
              className={styles.retryButton}
              disabled={busy || !activePreview}
              onClick={() => {
                if (pendingSaveModeRef.current) {
                  void handleSave(pendingSaveModeRef.current)
                }
              }}
            >
              Retry save
            </button>
          ) : null}
        </div>
      ) : null}

      {activePreview ? (
        <AnalysisPreview
          preview={activePreview}
          busy={saveMutation.isPending}
          onSave={() => {
            void handleSave('save')
          }}
          onSaveAndPrint={() => {
            void handleSave('save_and_print')
          }}
          onCancel={() => setConfirmCancel(true)}
        />
      ) : null}

      <div className={styles.grid}>
        <section className={styles.section} aria-label="Saved versions">
          <h3 className={styles.sectionHeading}>Saved versions</h3>
          <AnalysisVersionList
            versions={versions}
            selectedVersion={activePreview ? null : selectedVersion}
            loading={versionsQuery.isLoading && !versionsQuery.data}
            errorMessage={versionsError}
            onRetry={() => {
              void versionsQuery.refetch()
            }}
            onSelect={selectVersion}
          />
        </section>

        <div>
          {activePreview ? (
            <p className={styles.statusText} role="status">
              Review the unsaved temporary preview above. Saved versions remain
              unchanged until you Save.
            </p>
          ) : selectedVersion != null ? (
            <AnalysisVersionDetail
              caseUuid={caseUuid}
              versionNumber={selectedVersion}
              artifactUuid={lastArtifactUuid}
            />
          ) : (
            <p className={styles.empty}>
              Select a saved version or generate a temporary preview.
            </p>
          )}
        </div>
      </div>

      {confirmCancel ? (
        <div className={styles.confirmOverlay}>
          <div
            className={styles.confirmDialog}
            role="alertdialog"
            aria-modal="true"
            aria-labelledby="cancel-analysis-title"
          >
            <h3 id="cancel-analysis-title" className={styles.sectionHeading}>
              Discard temporary preview?
            </h3>
            <p className={styles.subhead}>
              Cancel discards this unsaved analysis. No version, artifact, or
              Official Case Record event will be created.
            </p>
            <div className={styles.confirmActions}>
              <button
                type="button"
                className={styles.secondaryButton}
                onClick={() => setConfirmCancel(false)}
              >
                Keep preview
              </button>
              <button
                type="button"
                className={styles.dangerButton}
                onClick={clearPreview}
              >
                Discard preview
              </button>
            </div>
          </div>
        </div>
      ) : null}
    </div>
  )
}
