import { useEffect, useId, useMemo, useRef, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { ApiError } from '../../api/client'
import type {
  SaveAndPrintStatus,
  TemporaryGrievanceDraft,
  WorkspaceActionAvailability,
} from '../../api/types/grievances'
import { useGenerateGrievanceMutation } from '../../features/cases/useGenerateGrievanceMutation'
import { useGrievanceArtifactsQuery } from '../../features/cases/useGrievanceArtifactsQuery'
import { useSaveGrievanceMutation } from '../../features/cases/useSaveGrievanceMutation'
import { validateTemporaryDraft } from '../../features/grievance/draftValidation'
import { getTemplateFields } from '../../features/grievance/templateFields'
import { GrievanceArtifactDetail } from './GrievanceArtifactDetail'
import { GrievanceArtifactList } from './GrievanceArtifactList'
import { GrievanceDraftEditor } from './GrievanceDraftEditor'
import styles from './GrievancePanel.module.css'

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
  return `m6-${Date.now()}-${Math.random().toString(36).slice(2, 10)}`
}

function findGenerateAvailability(
  availableActions: unknown[] | null | undefined,
): WorkspaceActionAvailability | null {
  if (!availableActions) return null
  for (const item of availableActions) {
    if (!item || typeof item !== 'object') continue
    const row = item as WorkspaceActionAvailability
    if (row.action === 'generate_grievance') {
      return row
    }
  }
  return null
}

export function GrievancePanel({
  caseUuid,
  savedBy,
  readOnly = false,
  availableActions,
}: Props) {
  const headingId = useId()
  const generateButtonRef = useRef<HTMLButtonElement | null>(null)
  const [searchParams, setSearchParams] = useSearchParams()
  const artifactsQuery = useGrievanceArtifactsQuery(caseUuid)
  const generateMutation = useGenerateGrievanceMutation()
  const saveMutation = useSaveGrievanceMutation()

  const [draft, setDraft] = useState<TemporaryGrievanceDraft | null>(null)
  const [draftCaseUuid, setDraftCaseUuid] = useState<string | null>(null)
  const [generateError, setGenerateError] = useState<string | null>(null)
  const [unsupportedNotice, setUnsupportedNotice] = useState<string | null>(
    null,
  )
  const [saveFeedback, setSaveFeedback] = useState<SaveFeedback | null>(null)
  const [saveError, setSaveError] = useState<string | null>(null)
  const [confirmCancel, setConfirmCancel] = useState(false)
  const [highlightInvalid, setHighlightInvalid] = useState(false)
  const idempotencyKeyRef = useRef<string | null>(null)
  const pendingSaveModeRef = useRef<SaveMode | null>(null)
  const abortRef = useRef<AbortController | null>(null)
  const caseUuidRef = useRef(caseUuid)
  caseUuidRef.current = caseUuid

  const selectedFromUrl = searchParams.get('artifact')

  const artifacts = artifactsQuery.data?.artifacts ?? []
  const selectedArtifactUuid =
    selectedFromUrl &&
    artifacts.some((item) => item.artifact_uuid === selectedFromUrl)
      ? selectedFromUrl
      : (artifacts[0]?.artifact_uuid ?? null)

  const activeDraft =
    draft && draftCaseUuid === caseUuid ? draft : null

  const validation = useMemo(
    () => (activeDraft ? validateTemporaryDraft(activeDraft) : null),
    [activeDraft],
  )

  useEffect(() => {
    abortRef.current?.abort()
    abortRef.current = null
    setDraft(null)
    setDraftCaseUuid(null)
    setGenerateError(null)
    setUnsupportedNotice(null)
    setSaveFeedback(null)
    setSaveError(null)
    setConfirmCancel(false)
    setHighlightInvalid(false)
    idempotencyKeyRef.current = null
    pendingSaveModeRef.current = null
  }, [caseUuid])

  useEffect(() => {
    if (!activeDraft || activeDraft.steward_override_field_ids.length === 0) {
      return
    }
    const onBeforeUnload = (event: BeforeUnloadEvent) => {
      event.preventDefault()
      event.returnValue = ''
    }
    window.addEventListener('beforeunload', onBeforeUnload)
    return () => window.removeEventListener('beforeunload', onBeforeUnload)
  }, [activeDraft])

  const generateAvailability = findGenerateAvailability(availableActions)
  const missingPrereqs =
    generateAvailability?.missing_prerequisites?.filter(
      (p) => p.message?.trim(),
    ) ?? []
  const generateBlocked =
    readOnly ||
    (generateAvailability != null && generateAvailability.available === false)

  const artifactsError =
    artifactsQuery.isError && !artifactsQuery.data
      ? artifactsQuery.error instanceof ApiError
        ? artifactsQuery.error.message
        : 'Unable to load saved grievances.'
      : null

  function selectArtifact(artifactUuid: string) {
    const next = new URLSearchParams(searchParams)
    next.set('artifact', artifactUuid)
    setSearchParams(next, { replace: true })
  }

  function clearDraft() {
    setDraft(null)
    setDraftCaseUuid(null)
    setConfirmCancel(false)
    setHighlightInvalid(false)
    idempotencyKeyRef.current = null
    pendingSaveModeRef.current = null
    generateButtonRef.current?.focus()
  }

  function handleFieldChange(fieldId: string, value: string) {
    setDraft((current) => {
      if (!current || draftCaseUuid !== caseUuid) return current
      const nextValues = { ...current.field_values, [fieldId]: value }
      const overrides = new Set(current.steward_override_field_ids)
      const generated = current.generated_field_values[fieldId] ?? ''
      if (value === generated) {
        overrides.delete(fieldId)
      } else {
        overrides.add(fieldId)
      }
      return {
        ...current,
        field_values: nextValues,
        steward_override_field_ids: Array.from(overrides),
      }
    })
  }

  function focusFirstInvalid(missingIds: string[]) {
    const first = missingIds[0]
    if (!first) return
    const el = document.getElementById(`grievance-field-${first}`)
    if (el && 'focus' in el) {
      ;(el as HTMLElement).focus()
    }
  }

  function handleValidate() {
    if (!activeDraft || !validation) return
    setHighlightInvalid(true)
    if (validation.missingRequiredFieldIds.length > 0) {
      focusFirstInvalid(validation.missingRequiredFieldIds)
    }
  }

  async function handleGenerate() {
    if (generateMutation.isPending || generateBlocked) return
    setGenerateError(null)
    setUnsupportedNotice(null)
    setSaveFeedback(null)
    setSaveError(null)
    setHighlightInvalid(false)

    abortRef.current?.abort()
    const controller = new AbortController()
    abortRef.current = controller
    const requestCaseUuid = caseUuid

    try {
      const result = await generateMutation.mutateAsync({
        caseUuid,
        signal: controller.signal,
      })
      if (caseUuidRef.current !== requestCaseUuid) return

      if (result.prerequisitesNotMet) {
        const messages =
          result.response.missing_prerequisites
            ?.map((p) => p.message)
            .filter(Boolean) ?? []
        setGenerateError(
          messages.join(' ') ||
            result.response.message ||
            'Generate Grievance prerequisites are not met.',
        )
        return
      }

      if (result.unsupportedTemplateId) {
        setUnsupportedNotice(
          `Official grievance generation for this workflow step is not available in the current product (template: ${result.unsupportedTemplateId}). Only Step 1 and Step 2 official forms are supported.`,
        )
        setDraft(null)
        setDraftCaseUuid(null)
        return
      }

      if (!result.draft) {
        setGenerateError('Generate Grievance returned no editable draft.')
        return
      }

      // Ensure all template fields exist in the map (blank if omitted).
      const fields = getTemplateFields(result.draft.template_id)
      const fieldValues = { ...result.draft.field_values }
      for (const field of fields) {
        if (!(field.id in fieldValues)) {
          fieldValues[field.id] = ''
        }
      }

      setDraft({
        ...result.draft,
        field_values: fieldValues,
        generated_field_values: { ...fieldValues },
      })
      setDraftCaseUuid(caseUuid)
      generateButtonRef.current?.focus()
    } catch (err) {
      if (err instanceof DOMException && err.name === 'AbortError') return
      if (caseUuidRef.current !== requestCaseUuid) return
      setGenerateError(
        err instanceof ApiError
          ? err.message
          : 'Unable to generate grievance draft.',
      )
    }
  }

  async function handleSave(mode: SaveMode) {
    if (!activeDraft || !validation || saveMutation.isPending) return
    setSaveError(null)
    setSaveFeedback(null)
    setHighlightInvalid(true)

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
          template_id: activeDraft.template_id,
          grievance_step: activeDraft.step_type ?? undefined,
          field_values: activeDraft.field_values,
          steward_override_field_ids: activeDraft.steward_override_field_ids,
          missing_required_field_ids: validation.missingRequiredFieldIds,
          validation_status: validation.clientDraftStatus,
          draft_status: validation.clientDraftStatus,
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
      clearDraft()

      const artifactUuid = result.artifact?.artifact_uuid
      if (artifactUuid) {
        selectArtifact(artifactUuid)
      }
    } catch (err) {
      setSaveError(
        err instanceof ApiError
          ? err.message
          : 'Unable to save the grievance.',
      )
    }
  }

  const busy = generateMutation.isPending || saveMutation.isPending

  return (
    <div className={styles.panel}>
      <header className={styles.header}>
        <h2 id={headingId} className={styles.heading}>
          Grievance
        </h2>
        <p className={styles.subhead}>
          Explicit Generate creates a temporary editable draft for the official
          Step 1 worksheet or Step 2 standard form. Save creates an official
          grievance artifact. Conversation and Analysis never create grievances.
        </p>
      </header>

      <div className={styles.toolbar}>
        <button
          ref={generateButtonRef}
          type="button"
          className={styles.primaryButton}
          disabled={busy || generateBlocked || Boolean(activeDraft)}
          aria-busy={generateMutation.isPending}
          onClick={() => {
            void handleGenerate()
          }}
        >
          {generateMutation.isPending
            ? 'Generating grievance…'
            : 'Generate Grievance'}
        </button>
        {generateBlocked ? (
          <p className={styles.statusText} role="status">
            {readOnly
              ? 'Case is closed, settled, or archived. Reopen before generating a grievance.'
              : generateAvailability?.reason ||
                'Generate Grievance prerequisites are not met.'}
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

      {unsupportedNotice ? (
        <div className={styles.warningBox} role="status">
          {unsupportedNotice}
        </div>
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
              ? 'Grievance saved successfully, but PDF preparation failed. The official artifact was not lost — retry PDF from the saved entry.'
              : saveFeedback.status === 'idempotent_replay'
                ? 'Save replayed safely — no duplicate grievance artifact was created.'
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
              disabled={busy || !activeDraft}
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

      {activeDraft && validation ? (
        <GrievanceDraftEditor
          draft={activeDraft}
          validation={validation}
          busy={saveMutation.isPending}
          highlightInvalid={highlightInvalid}
          onChangeField={handleFieldChange}
          onSave={() => {
            void handleSave('save')
          }}
          onSaveAndPrint={() => {
            void handleSave('save_and_print')
          }}
          onCancel={() => {
            if (activeDraft.steward_override_field_ids.length > 0) {
              setConfirmCancel(true)
            } else {
              clearDraft()
            }
          }}
          onValidate={handleValidate}
        />
      ) : null}

      <div className={styles.grid}>
        <section className={styles.section} aria-label="Saved grievances">
          <h3 className={styles.sectionHeading}>Saved grievances</h3>
          <GrievanceArtifactList
            artifacts={artifacts}
            selectedArtifactUuid={activeDraft ? null : selectedArtifactUuid}
            loading={artifactsQuery.isLoading && !artifactsQuery.data}
            errorMessage={artifactsError}
            onRetry={() => {
              void artifactsQuery.refetch()
            }}
            onSelect={selectArtifact}
          />
        </section>

        <div>
          {activeDraft ? (
            <p className={styles.statusText} role="status">
              Review the unsaved temporary draft above. Saved grievances remain
              unchanged until you Save.
            </p>
          ) : selectedArtifactUuid ? (
            <GrievanceArtifactDetail
              caseUuid={caseUuid}
              artifactUuid={selectedArtifactUuid}
            />
          ) : (
            <p className={styles.empty}>
              Select a saved grievance or generate a temporary draft.
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
            aria-labelledby="cancel-grievance-title"
          >
            <h3 id="cancel-grievance-title" className={styles.sectionHeading}>
              Discard unsaved grievance draft?
            </h3>
            <p className={styles.subhead}>
              Cancel discards this temporary draft. No artifact, PDF, or
              Official Case Record event will be created.
            </p>
            <div className={styles.confirmActions}>
              <button
                type="button"
                className={styles.secondaryButton}
                onClick={() => setConfirmCancel(false)}
              >
                Keep draft
              </button>
              <button
                type="button"
                className={styles.dangerButton}
                onClick={clearDraft}
              >
                Discard draft
              </button>
            </div>
          </div>
        </div>
      ) : null}
    </div>
  )
}
