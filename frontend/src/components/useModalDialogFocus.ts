import { useEffect, useRef } from 'react'

const FOCUSABLE_SELECTOR = [
  'a[href]',
  'button:not([disabled])',
  'input:not([disabled])',
  'select:not([disabled])',
  'textarea:not([disabled])',
  '[tabindex]:not([tabindex="-1"])',
].join(',')

type Options = {
  open: boolean
  onClose: () => void
  escapeDisabled?: boolean
}

function focusableElements(container: HTMLElement): HTMLElement[] {
  return Array.from(
    container.querySelectorAll<HTMLElement>(FOCUSABLE_SELECTOR),
  ).filter((element) => !element.hidden && element.getAttribute('aria-hidden') !== 'true')
}

/**
 * Native modal-dialog focus behavior without adding an accessibility dependency.
 * Focus enters the dialog, Tab stays inside, Escape closes when allowed, and
 * focus returns to the control that opened the dialog.
 */
export function useModalDialogFocus({
  open,
  onClose,
  escapeDisabled = false,
}: Options) {
  const dialogRef = useRef<HTMLDivElement>(null)
  const onCloseRef = useRef(onClose)
  onCloseRef.current = onClose

  useEffect(() => {
    if (!open) return

    const previous = document.activeElement as HTMLElement | null
    const dialog = dialogRef.current
    if (!dialog) return
    const activeDialog: HTMLDivElement = dialog

    const initial = focusableElements(activeDialog)[0] ?? activeDialog
    initial.focus()

    function onKeyDown(event: KeyboardEvent) {
      if (event.key === 'Escape' && !escapeDisabled) {
        event.preventDefault()
        onCloseRef.current()
        return
      }
      if (event.key !== 'Tab') return

      const elements = focusableElements(activeDialog)
      if (elements.length === 0) {
        event.preventDefault()
        activeDialog.focus()
        return
      }

      const first = elements[0]!
      const last = elements[elements.length - 1]!
      const active = document.activeElement
      if (event.shiftKey && (active === first || !activeDialog.contains(active))) {
        event.preventDefault()
        last.focus()
      } else if (
        !event.shiftKey &&
        (active === last || !activeDialog.contains(active))
      ) {
        event.preventDefault()
        first.focus()
      }
    }

    document.addEventListener('keydown', onKeyDown)
    return () => {
      document.removeEventListener('keydown', onKeyDown)
      if (previous?.isConnected) {
        previous.focus()
      }
    }
  }, [open, escapeDisabled])

  return dialogRef
}
