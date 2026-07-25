import { useId, type KeyboardEvent } from 'react'
import styles from './ConversationPanel.module.css'

type Props = {
  value: string
  disabled?: boolean
  pending?: boolean
  readOnlyReason?: string | null
  onChange: (value: string) => void
  onSubmit: () => void
}

export function ConversationComposer({
  value,
  disabled = false,
  pending = false,
  readOnlyReason,
  onChange,
  onSubmit,
}: Props) {
  const labelId = useId()
  const helpId = useId()
  const busy = pending || disabled

  function handleKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault()
      if (!busy && value.trim().length > 0) {
        onSubmit()
      }
    }
  }

  return (
    <form
      className={styles.composer}
      aria-busy={pending || undefined}
      onSubmit={(event) => {
        event.preventDefault()
        if (!busy && value.trim().length > 0) {
          onSubmit()
        }
      }}
    >
      <label id={labelId} className={styles.composerLabel} htmlFor="conversation-composer">
        Message
      </label>
      <p id={helpId} className={styles.composerHelp}>
        Conversation does not create an analysis report or grievance.
        {readOnlyReason ? ` ${readOnlyReason}` : ''}
      </p>
      <textarea
        id="conversation-composer"
        className={styles.composerInput}
        name="conversation-message"
        value={value}
        disabled={busy || Boolean(readOnlyReason)}
        aria-labelledby={labelId}
        aria-describedby={helpId}
        onChange={(event) => onChange(event.target.value)}
        onKeyDown={handleKeyDown}
      />
      <div className={styles.composerActions}>
        <p className={styles.composerHint}>
          Enter sends · Shift+Enter for a new line
        </p>
        <button
          type="submit"
          className={styles.sendButton}
          disabled={busy || value.trim().length === 0 || Boolean(readOnlyReason)}
          aria-label="Send message"
        >
          {pending ? 'Sending…' : 'Send'}
        </button>
      </div>
    </form>
  )
}
