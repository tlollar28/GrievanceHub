import { useEffect, useId, useState, type FormEvent } from 'react'
import { ApiError } from '../../api/client'
import {
  OUTCOME_TYPE_VALUES,
  type OutcomeType,
  type RecordStepOutcomeRequest,
} from '../../api/types/workflow'
import { useRecordOutcomeMutation } from '../../features/cases/useRecordOutcomeMutation'
import {
  describeOutcomeEffect,
  outcomeTypeLabel,
} from '../../features/workflow/workflowLabels'
import { ConfirmActionDialog } from './ConfirmActionDialog'
import styles from './WorkflowPanel.module.css'

export type OutcomeFormValues = {
  outcome_type: OutcomeType
  decision_summary: string
  decision_date: string
  steward_notes: string
  decision_document_refs: string
  close_step: boolean
  close_case: boolean
  appeal_to_next_step: boolean
  resolution_type: string
  closed_by: string
}

const EMPTY_FORM: OutcomeFormValues = {
  outcome_type: 'pending',
  decision_summary: '',
  decision_date: '',
  steward_notes: '',
  decision_document_refs: '',
  close_step: false,
  close_case: false,
  appeal_to_next_step: false,
  resolution_type: '',
  closed_by: '',
}

type Props = {
  caseUuid: string
  caseTitle: string
  currentStepType: string | null
  disabled?: boolean
  onSuccess?: () => void
}

export function RecordOutcomeForm({
  caseUuid,
  caseTitle,
  currentStepType,
  disabled = false,
  onSuccess,
}: Props) {
  const formId = useId()
  const [values, setValues] = useState<OutcomeFormValues>(EMPTY_FORM)
  const [clientErrors, setClientErrors] = useState<string[]>([])
  const [confirmOpen, setConfirmOpen] = useState(false)
  const [successMessage, setSuccessMessage] = useState<string | null>(null)
  const mutation = useRecordOutcomeMutation(caseUuid)

  useEffect(() => {
    setValues(EMPTY_FORM)
    setClientErrors([])
    setConfirmOpen(false)
    setSuccessMessage(null)
    mutation.reset()
    // Reset local form when switching cases; do not depend on mutation identity.
    // eslint-disable-next-line react-hooks/exhaustive-deps -- intentional caseUuid-only reset
  }, [caseUuid])

  const effectText = describeOutcomeEffect({
    outcomeType: values.outcome_type,
    closeStep: values.close_step,
    closeCase: values.close_case,
    appealToNextStep: values.appeal_to_next_step,
  })

  const needsConfirmation =
    values.close_step ||
    values.close_case ||
    values.appeal_to_next_step ||
    values.outcome_type === 'settled'

  function validate(): string[] {
    const errors: string[] = []
    if (!values.outcome_type) {
      errors.push('Outcome type is required.')
    }
    if (!values.decision_summary.trim()) {
      errors.push('Decision summary is required.')
    }
    if (values.close_case && !values.resolution_type.trim()) {
      errors.push(
        'Resolution type is required when closing the case from this outcome.',
      )
    }
    if (values.appeal_to_next_step && values.close_case) {
      errors.push('Choose either appeal to next step or close case, not both.')
    }
    return errors
  }

  function buildRequest(): RecordStepOutcomeRequest {
    const refs = values.decision_document_refs
      .split(/[\n,]/)
      .map((item) => item.trim())
      .filter(Boolean)
    return {
      step_type: currentStepType,
      outcome_type: values.outcome_type,
      decision_summary: values.decision_summary.trim(),
      decision_date: values.decision_date.trim() || null,
      steward_notes: values.steward_notes.trim() || null,
      close_step: values.close_step,
      close_case: values.close_case,
      appeal_to_next_step: values.appeal_to_next_step,
      decision_document_refs: refs,
      resolution_type: values.resolution_type.trim() || null,
      closed_by: values.closed_by.trim() || null,
    }
  }

  function handleSubmit(event: FormEvent) {
    event.preventDefault()
    setSuccessMessage(null)
    const errors = validate()
    setClientErrors(errors)
    if (errors.length > 0) return
    if (needsConfirmation) {
      setConfirmOpen(true)
      return
    }
    void submitOutcome()
  }

  async function submitOutcome() {
    try {
      await mutation.mutateAsync(buildRequest())
      setValues(EMPTY_FORM)
      setClientErrors([])
      setConfirmOpen(false)
      setSuccessMessage('Outcome recorded. Workflow and history refreshed.')
      onSuccess?.()
    } catch {
      setConfirmOpen(false)
      // Preserve form values after failure.
    }
  }

  const apiError =
    mutation.isError && mutation.error instanceof ApiError
      ? mutation.error.message
      : mutation.isError
        ? 'Unable to record the outcome.'
        : null

  const busy = mutation.isPending || disabled

  return (
    <section
      className={styles.section}
      aria-labelledby={`${formId}-heading`}
    >
      <h3 id={`${formId}-heading`} className={styles.sectionHeading}>
        Record outcome
      </h3>
      <p className={styles.fieldHint}>
        Steward-recorded management decision for the current step. Does not
        create analysis or grievance artifacts.
      </p>

      <form className={styles.form} onSubmit={handleSubmit} noValidate>
        <div className={styles.field}>
          <label className={styles.fieldLabel} htmlFor={`${formId}-outcome`}>
            Outcome type
          </label>
          <select
            id={`${formId}-outcome`}
            className={styles.select}
            value={values.outcome_type}
            disabled={busy}
            onChange={(event) =>
              setValues((prev) => ({
                ...prev,
                outcome_type: event.target.value as OutcomeType,
              }))
            }
          >
            {OUTCOME_TYPE_VALUES.map((type) => (
              <option key={type} value={type}>
                {outcomeTypeLabel(type)}
              </option>
            ))}
          </select>
        </div>

        <div className={styles.field}>
          <label className={styles.fieldLabel} htmlFor={`${formId}-summary`}>
            Decision summary
          </label>
          <textarea
            id={`${formId}-summary`}
            className={styles.textarea}
            value={values.decision_summary}
            disabled={busy}
            required
            aria-required="true"
            onChange={(event) =>
              setValues((prev) => ({
                ...prev,
                decision_summary: event.target.value,
              }))
            }
          />
        </div>

        <div className={styles.field}>
          <label className={styles.fieldLabel} htmlFor={`${formId}-date`}>
            Decision date
          </label>
          <input
            id={`${formId}-date`}
            className={styles.input}
            type="date"
            value={values.decision_date}
            disabled={busy}
            onChange={(event) =>
              setValues((prev) => ({
                ...prev,
                decision_date: event.target.value,
              }))
            }
          />
          <p className={styles.fieldHint} id={`${formId}-date-hint`}>
            Optional steward-supplied date. Never invented by the system.
          </p>
        </div>

        <div className={styles.field}>
          <label className={styles.fieldLabel} htmlFor={`${formId}-notes`}>
            Steward notes
          </label>
          <textarea
            id={`${formId}-notes`}
            className={styles.textarea}
            value={values.steward_notes}
            disabled={busy}
            onChange={(event) =>
              setValues((prev) => ({
                ...prev,
                steward_notes: event.target.value,
              }))
            }
          />
        </div>

        <div className={styles.field}>
          <label className={styles.fieldLabel} htmlFor={`${formId}-refs`}>
            Decision document references
          </label>
          <textarea
            id={`${formId}-refs`}
            className={styles.textarea}
            value={values.decision_document_refs}
            disabled={busy}
            placeholder="Optional asset UUIDs or references, one per line"
            onChange={(event) =>
              setValues((prev) => ({
                ...prev,
                decision_document_refs: event.target.value,
              }))
            }
          />
        </div>

        <fieldset className={styles.field} disabled={busy}>
          <legend className={styles.fieldLabel}>Deliberate effects</legend>
          <p className={styles.fieldHint} id={`${formId}-effects-hint`}>
            These flags are not inferred. Select them only when intended.
          </p>
          <label className={styles.checkboxRow}>
            <input
              type="checkbox"
              checked={values.close_step}
              aria-describedby={`${formId}-effects-hint`}
              onChange={(event) =>
                setValues((prev) => ({
                  ...prev,
                  close_step: event.target.checked,
                }))
              }
            />
            <span>Close current step</span>
          </label>
          <label className={styles.checkboxRow}>
            <input
              type="checkbox"
              checked={values.appeal_to_next_step}
              onChange={(event) =>
                setValues((prev) => ({
                  ...prev,
                  appeal_to_next_step: event.target.checked,
                  close_case: event.target.checked ? false : prev.close_case,
                }))
              }
            />
            <span>Appeal to next step (same case UUID)</span>
          </label>
          <label className={styles.checkboxRow}>
            <input
              type="checkbox"
              checked={values.close_case}
              onChange={(event) =>
                setValues((prev) => ({
                  ...prev,
                  close_case: event.target.checked,
                  appeal_to_next_step: event.target.checked
                    ? false
                    : prev.appeal_to_next_step,
                }))
              }
            />
            <span>Close case</span>
          </label>
        </fieldset>

        {values.close_case ? (
          <>
            <div className={styles.field}>
              <label
                className={styles.fieldLabel}
                htmlFor={`${formId}-resolution`}
              >
                Resolution type
              </label>
              <input
                id={`${formId}-resolution`}
                className={styles.input}
                value={values.resolution_type}
                disabled={busy}
                required
                aria-required="true"
                placeholder="e.g. resolved, withdrawn, denied_final"
                onChange={(event) =>
                  setValues((prev) => ({
                    ...prev,
                    resolution_type: event.target.value,
                  }))
                }
              />
            </div>
            <div className={styles.field}>
              <label
                className={styles.fieldLabel}
                htmlFor={`${formId}-closed-by`}
              >
                Closed by
              </label>
              <input
                id={`${formId}-closed-by`}
                className={styles.input}
                value={values.closed_by}
                disabled={busy}
                onChange={(event) =>
                  setValues((prev) => ({
                    ...prev,
                    closed_by: event.target.value,
                  }))
                }
              />
            </div>
          </>
        ) : null}

        <div className={styles.effectBox} role="note">
          <strong>Effect before submit:</strong> {effectText}
        </div>

        {clientErrors.length > 0 ? (
          <div
            className={styles.errorSummary}
            role="alert"
            aria-labelledby={`${formId}-error-summary`}
          >
            <strong id={`${formId}-error-summary`}>
              Fix the following before recording:
            </strong>
            <ul>
              {clientErrors.map((error) => (
                <li key={error}>{error}</li>
              ))}
            </ul>
          </div>
        ) : null}

        {apiError ? (
          <p className={styles.errorSummary} role="alert">
            {apiError}
          </p>
        ) : null}

        {successMessage ? (
          <p role="status">{successMessage}</p>
        ) : null}

        <div className={styles.actions}>
          <button
            type="submit"
            className={styles.button}
            disabled={busy}
            aria-busy={mutation.isPending}
          >
            {mutation.isPending ? 'Recording…' : 'Record outcome'}
          </button>
        </div>
      </form>

      <ConfirmActionDialog
        open={confirmOpen}
        title={`Confirm outcome for ${caseTitle}`}
        description={
          values.appeal_to_next_step
            ? `Appeal this case to the next step while keeping case UUID ${caseUuid}. Prior step history remains.`
            : values.close_case
              ? `Close case ${caseUuid}. Prior history and artifacts remain. You can reopen later.`
              : values.close_step
                ? `Close the current step on case ${caseUuid}.`
                : `Record a settled outcome for case ${caseUuid}.`
        }
        confirmLabel="Confirm and record"
        busy={mutation.isPending}
        destructive={values.close_case}
        onCancel={() => setConfirmOpen(false)}
        onConfirm={() => {
          void submitOutcome()
        }}
      />
    </section>
  )
}
