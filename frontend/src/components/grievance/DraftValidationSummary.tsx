import type { DraftValidationView } from '../../features/grievance/draftValidation'
import { fieldLabel } from '../../features/grievance/draftValidation'
import styles from './GrievancePanel.module.css'

type Props = {
  validation: DraftValidationView
  serverDraftStatus: string | null | undefined
  showInvalidFocusHint?: boolean
}

export function DraftValidationSummary({
  validation,
  serverDraftStatus,
  showInvalidFocusHint = false,
}: Props) {
  return (
    <section
      className={styles.validationSummary}
      aria-label="Draft validation summary"
    >
      <h3 className={styles.sectionHeading}>Draft validation</h3>
      <p className={styles.fieldHint}>
        Client checks are early feedback only. The backend remains authoritative
        on Save.
      </p>
      <dl className={styles.metaRow}>
        <div>
          <dt className={styles.kindLabel}>Server draft status</dt>
          <dd>{serverDraftStatus ?? '—'}</dd>
        </div>
        <div>
          <dt className={styles.kindLabel}>Client status</dt>
          <dd>{validation.clientDraftStatus}</dd>
        </div>
        <div>
          <dt className={styles.kindLabel}>Save</dt>
          <dd>
            {validation.savePermitted
              ? 'Permitted (incomplete drafts may be saved)'
              : 'Not permitted'}
          </dd>
        </div>
        <div>
          <dt className={styles.kindLabel}>Save and Print</dt>
          <dd>
            {validation.saveAndPrintPermitted
              ? 'Permitted'
              : 'Not permitted'}
          </dd>
        </div>
      </dl>

      {validation.readyForStewardReview ? (
        <p className={styles.successBox} role="status">
          Required fields are filled. Ready fields: {validation.readyFieldIds.length}.
        </p>
      ) : (
        <div className={styles.warningBox} role="status">
          <p>
            Missing required fields ({validation.missingRequiredFieldIds.length}
            ). Form is not classified as ready.
          </p>
          {showInvalidFocusHint ? (
            <p>Focus moved to the first missing required field.</p>
          ) : null}
          <ul className={styles.validationList}>
            {validation.missingRequiredFieldIds.map((id) => (
              <li key={id}>{fieldLabel(id, validation.fields)}</li>
            ))}
          </ul>
        </div>
      )}

      {validation.protectedBlankFieldIds.length > 0 ? (
        <div className={styles.warningBox} role="status">
          <p>
            Protected fields left blank — automated generation must not invent
            these values. Supply them only when known:
          </p>
          <ul className={styles.validationList}>
            {validation.protectedBlankFieldIds.map((id) => (
              <li key={id}>{fieldLabel(id, validation.fields)}</li>
            ))}
          </ul>
        </div>
      ) : null}
    </section>
  )
}
