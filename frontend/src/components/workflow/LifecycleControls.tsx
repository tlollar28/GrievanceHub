import { useEffect, useId, useState } from 'react'
import { ApiError } from '../../api/client'
import {
  useArchiveCaseMutation,
  useCloseCaseMutation,
  useReopenCaseMutation,
  useSettleCaseMutation,
} from '../../features/cases/useCaseLifecycleMutations'
import { isTerminalCaseStatus } from '../../features/workflow/workflowLabels'
import { ConfirmActionDialog } from './ConfirmActionDialog'
import styles from './WorkflowPanel.module.css'

type LifecycleAction = 'close' | 'settle' | 'archive' | 'reopen' | null

type Props = {
  caseUuid: string
  caseTitle: string
  caseStatus: string | null
}

export function LifecycleControls({
  caseUuid,
  caseTitle,
  caseStatus,
}: Props) {
  const formId = useId()
  const [pendingAction, setPendingAction] = useState<LifecycleAction>(null)
  const [closeOutcome, setCloseOutcome] = useState('')
  const [closeResolution, setCloseResolution] = useState('resolved')
  const [closeNotes, setCloseNotes] = useState('')
  const [settleNotes, setSettleNotes] = useState('')
  const [settleDate, setSettleDate] = useState('')
  const [settleBy, setSettleBy] = useState('')
  const [archiveReason, setArchiveReason] = useState('')
  const [statusMessage, setStatusMessage] = useState<string | null>(null)
  const [errorMessage, setErrorMessage] = useState<string | null>(null)

  const closeMutation = useCloseCaseMutation(caseUuid)
  const settleMutation = useSettleCaseMutation(caseUuid)
  const archiveMutation = useArchiveCaseMutation(caseUuid)
  const reopenMutation = useReopenCaseMutation(caseUuid)

  useEffect(() => {
    setPendingAction(null)
    setCloseOutcome('')
    setCloseResolution('resolved')
    setCloseNotes('')
    setSettleNotes('')
    setSettleDate('')
    setSettleBy('')
    setArchiveReason('')
    setStatusMessage(null)
    setErrorMessage(null)
    closeMutation.reset()
    settleMutation.reset()
    archiveMutation.reset()
    reopenMutation.reset()
    // eslint-disable-next-line react-hooks/exhaustive-deps -- intentional caseUuid-only reset
  }, [caseUuid])

  const terminal = isTerminalCaseStatus(caseStatus)
  const busy =
    closeMutation.isPending ||
    settleMutation.isPending ||
    archiveMutation.isPending ||
    reopenMutation.isPending

  async function runConfirmedAction() {
    setErrorMessage(null)
    setStatusMessage(null)
    try {
      if (pendingAction === 'close') {
        if (!closeOutcome.trim() || !closeResolution.trim()) {
          setErrorMessage('Close requires outcome and resolution type.')
          setPendingAction(null)
          return
        }
        await closeMutation.mutateAsync({
          outcome: closeOutcome.trim(),
          resolution_type: closeResolution.trim(),
          outcome_notes: closeNotes.trim() || null,
        })
        setStatusMessage('Case closed. History and artifacts remain.')
      } else if (pendingAction === 'settle') {
        await settleMutation.mutateAsync({
          settlement_notes: settleNotes.trim() || null,
          settlement_date: settleDate
            ? new Date(`${settleDate}T12:00:00`).toISOString()
            : null,
          settled_by: settleBy.trim() || null,
        })
        setStatusMessage('Case settled. History and artifacts remain.')
      } else if (pendingAction === 'archive') {
        const reason = archiveReason.trim()
        await archiveMutation.mutateAsync(
          reason
            ? { status: 'archived', reason }
            : null,
        )
        setStatusMessage(
          'Case archived. It remains discoverable in Saved Cases.',
        )
      } else if (pendingAction === 'reopen') {
        await reopenMutation.mutateAsync({ source: 'manual_ui' })
        setStatusMessage(
          'Case reopened on the same case UUID. Prior history remains.',
        )
      }
      setPendingAction(null)
    } catch (error) {
      setPendingAction(null)
      setErrorMessage(
        error instanceof ApiError
          ? error.message
          : 'Lifecycle action failed.',
      )
    }
  }

  const confirmCopy = (() => {
    switch (pendingAction) {
      case 'close':
        return {
          title: `Close case ${caseTitle}`,
          description: `Close case ${caseUuid}. Prior history and artifacts remain. You can reopen later through Saved Cases or this page.`,
          confirmLabel: 'Close case',
          destructive: true,
        }
      case 'settle':
        return {
          title: `Settle case ${caseTitle}`,
          description: `Mark case ${caseUuid} as settled. Prior history and artifacts remain. This does not create a settlement document workflow.`,
          confirmLabel: 'Settle case',
          destructive: true,
        }
      case 'archive':
        return {
          title: `Archive case ${caseTitle}`,
          description: `Archive case ${caseUuid}. The case remains part of saved history and is not permanently deleted.`,
          confirmLabel: 'Archive case',
          destructive: true,
        }
      case 'reopen':
        return {
          title: `Reopen case ${caseTitle}`,
          description: `Reopen case ${caseUuid} using the existing Saved Cases lifecycle path. Messages, memory, evidence, artifacts, and outcomes remain.`,
          confirmLabel: 'Reopen case',
          destructive: false,
        }
      default:
        return null
    }
  })()

  return (
    <section className={styles.section} aria-labelledby={`${formId}-heading`}>
      <h3 id={`${formId}-heading`} className={styles.sectionHeading}>
        Case lifecycle
      </h3>
      <p className={styles.fieldHint}>
        Explicit close, settle, and archive use the saved-case lifecycle routes.
        Outcome recording above is for step decisions and same-case appeal.
      </p>

      {terminal ? (
        <div className={styles.statusBanner} role="status">
          This case is terminal ({caseStatus}). Workflow mutations that advance
          an open case are unavailable until reopen.
        </div>
      ) : null}

      <div className={styles.lifecycleGrid}>
        {!terminal ? (
          <>
            <div className={styles.lifecycleCard}>
              <strong>Close case</strong>
              <p>Requires outcome and resolution type. History remains.</p>
              <label className={styles.fieldLabel} htmlFor={`${formId}-outcome`}>
                Outcome
              </label>
              <input
                id={`${formId}-outcome`}
                className={styles.input}
                value={closeOutcome}
                disabled={busy}
                onChange={(event) => setCloseOutcome(event.target.value)}
              />
              <label
                className={styles.fieldLabel}
                htmlFor={`${formId}-resolution`}
              >
                Resolution type
              </label>
              <input
                id={`${formId}-resolution`}
                className={styles.input}
                value={closeResolution}
                disabled={busy}
                onChange={(event) => setCloseResolution(event.target.value)}
              />
              <label className={styles.fieldLabel} htmlFor={`${formId}-notes`}>
                Notes (optional)
              </label>
              <textarea
                id={`${formId}-notes`}
                className={styles.textarea}
                value={closeNotes}
                disabled={busy}
                onChange={(event) => setCloseNotes(event.target.value)}
              />
              <button
                type="button"
                className={styles.dangerButton}
                disabled={busy}
                onClick={() => setPendingAction('close')}
              >
                Close case…
              </button>
            </div>

            <div className={styles.lifecycleCard}>
              <strong>Settle case</strong>
              <p>Optional settlement summary and date. No document workflow.</p>
              <label
                className={styles.fieldLabel}
                htmlFor={`${formId}-settle-notes`}
              >
                Settlement notes
              </label>
              <textarea
                id={`${formId}-settle-notes`}
                className={styles.textarea}
                value={settleNotes}
                disabled={busy}
                onChange={(event) => setSettleNotes(event.target.value)}
              />
              <label
                className={styles.fieldLabel}
                htmlFor={`${formId}-settle-date`}
              >
                Settlement date
              </label>
              <input
                id={`${formId}-settle-date`}
                type="date"
                className={styles.input}
                value={settleDate}
                disabled={busy}
                onChange={(event) => setSettleDate(event.target.value)}
              />
              <label
                className={styles.fieldLabel}
                htmlFor={`${formId}-settle-by`}
              >
                Settled by
              </label>
              <input
                id={`${formId}-settle-by`}
                className={styles.input}
                value={settleBy}
                disabled={busy}
                onChange={(event) => setSettleBy(event.target.value)}
              />
              <button
                type="button"
                className={styles.dangerButton}
                disabled={busy}
                onClick={() => setPendingAction('settle')}
              >
                Settle case…
              </button>
            </div>

            <div className={styles.lifecycleCard}>
              <strong>Archive case</strong>
              <p>Remains in Saved Cases history. Not permanently deleted.</p>
              <label
                className={styles.fieldLabel}
                htmlFor={`${formId}-archive-reason`}
              >
                Reason (optional)
              </label>
              <input
                id={`${formId}-archive-reason`}
                className={styles.input}
                value={archiveReason}
                disabled={busy}
                onChange={(event) => setArchiveReason(event.target.value)}
              />
              <button
                type="button"
                className={styles.dangerButton}
                disabled={busy}
                onClick={() => setPendingAction('archive')}
              >
                Archive case…
              </button>
            </div>
          </>
        ) : (
          <div className={styles.lifecycleCard}>
            <strong>Reopen case</strong>
            <p>
              Uses the existing Saved Cases reopen path. Same case UUID and
              prior history remain.
            </p>
            <button
              type="button"
              className={styles.button}
              disabled={busy}
              onClick={() => setPendingAction('reopen')}
            >
              Reopen case…
            </button>
          </div>
        )}
      </div>

      {errorMessage ? (
        <p className={styles.errorSummary} role="alert">
          {errorMessage}
        </p>
      ) : null}
      {statusMessage ? <p role="status">{statusMessage}</p> : null}

      {confirmCopy ? (
        <ConfirmActionDialog
          open={pendingAction !== null}
          title={confirmCopy.title}
          description={confirmCopy.description}
          confirmLabel={confirmCopy.confirmLabel}
          destructive={confirmCopy.destructive}
          busy={busy}
          onCancel={() => setPendingAction(null)}
          onConfirm={() => {
            void runConfirmedAction()
          }}
        />
      ) : null}
    </section>
  )
}
