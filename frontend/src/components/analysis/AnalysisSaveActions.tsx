import styles from './AnalysisPanel.module.css'

type Props = {
  disabled: boolean
  busy: boolean
  busyMode: 'save' | 'save_and_print' | null
  onSave: () => void
  onSaveAndPrint: () => void
  onCancel: () => void
}

export function AnalysisSaveActions({
  disabled,
  busy,
  busyMode,
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
        {busyMode === 'save' ? 'Saving analysis…' : 'Save'}
      </button>
      <button
        type="button"
        className={styles.primaryButton}
        disabled={disabled || busy}
        aria-busy={busy}
        onClick={onSaveAndPrint}
      >
        {busyMode === 'save_and_print'
          ? 'Saving and preparing PDF…'
          : 'Save and Print'}
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
