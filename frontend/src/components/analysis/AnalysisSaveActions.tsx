import styles from './AnalysisPanel.module.css'

type Props = {
  disabled: boolean
  busy: boolean
  onSave: () => void
  onSaveAndPrint: () => void
  onCancel: () => void
}

export function AnalysisSaveActions({
  disabled,
  busy,
  onSave,
  onSaveAndPrint,
  onCancel,
}: Props) {
  return (
    <div className={styles.toolbar} role="group" aria-label="Save analysis">
      <button
        type="button"
        className={styles.primaryButton}
        disabled={disabled || busy}
        aria-busy={busy}
        onClick={onSave}
      >
        Save
      </button>
      <button
        type="button"
        className={styles.primaryButton}
        disabled={disabled || busy}
        aria-busy={busy}
        onClick={onSaveAndPrint}
      >
        Save and Print
      </button>
      <button
        type="button"
        className={styles.dangerButton}
        disabled={busy}
        aria-label="Cancel temporary analysis preview"
        onClick={onCancel}
      >
        Cancel
      </button>
    </div>
  )
}
