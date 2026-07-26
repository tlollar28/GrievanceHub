import { useId } from 'react'
import { useModalDialogFocus } from '../useModalDialogFocus'
import styles from './WorkflowPanel.module.css'

type Props = {
  open: boolean
  title: string
  description: string
  confirmLabel: string
  busy?: boolean
  destructive?: boolean
  onConfirm: () => void
  onCancel: () => void
}

export function ConfirmActionDialog({
  open,
  title,
  description,
  confirmLabel,
  busy = false,
  destructive = false,
  onConfirm,
  onCancel,
}: Props) {
  const titleId = useId()
  const descId = useId()
  const dialogRef = useModalDialogFocus({
    open,
    onClose: onCancel,
    escapeDisabled: busy,
  })

  if (!open) return null

  return (
    <div
      className={styles.dialogBackdrop}
      role="presentation"
      onMouseDown={(event) => {
        if (event.target === event.currentTarget && !busy) onCancel()
      }}
    >
      <div
        ref={dialogRef}
        className={styles.dialog}
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        aria-describedby={descId}
        tabIndex={-1}
      >
        <h3 id={titleId} className={styles.sectionHeading}>
          {title}
        </h3>
        <p id={descId}>{description}</p>
        <div className={styles.dialogActions}>
          <button
            type="button"
            className={styles.secondaryButton}
            onClick={onCancel}
            disabled={busy}
          >
            Cancel
          </button>
          <button
            type="button"
            className={destructive ? styles.dangerButton : styles.button}
            onClick={onConfirm}
            disabled={busy}
            aria-busy={busy}
          >
            {busy ? 'Working…' : confirmLabel}
          </button>
        </div>
      </div>
    </div>
  )
}
