import styles from './GrievancePanel.module.css'

type Props = {
  busy: boolean
  dirty: boolean
  onSave: () => void
  onSaveAndPrint: () => void
  onCancel: () => void
  onValidate?: () => void
}

export function GrievanceSaveActions({
  busy,
  dirty,
  onSave,
  onSaveAndPrint,
  onCancel,
  onValidate,
}: Props) {
  return (
    <div className={styles.toolbar} role="group" aria-label="Grievance draft actions">
      {dirty ? (
        <span className={styles.dirtyBadge} role="status">
          Unsaved edits
        </span>
      ) : (
        <span className={styles.tempBadge} role="status">
          Temporary draft
        </span>
      )}
      {onValidate ? (
        <button
          type="button"
          className={styles.secondaryButton}
          disabled={busy}
          onClick={onValidate}
        >
          Validate
        </button>
      ) : null}
      <button
        type="button"
        className={styles.primaryButton}
        disabled={busy}
        aria-busy={busy}
        onClick={onSave}
      >
        {busy ? 'Saving…' : 'Save'}
      </button>
      <button
        type="button"
        className={styles.primaryButton}
        disabled={busy}
        aria-busy={busy}
        onClick={onSaveAndPrint}
      >
        {busy ? 'Saving…' : 'Save and Print'}
      </button>
      <button
        type="button"
        className={styles.dangerButton}
        disabled={busy}
        aria-label="Cancel temporary grievance draft"
        onClick={onCancel}
      >
        Cancel
      </button>
    </div>
  )
}
