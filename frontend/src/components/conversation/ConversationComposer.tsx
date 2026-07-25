import { useId, type KeyboardEvent } from 'react'
import { AttachmentPicker } from './AttachmentPicker'
import styles from './ConversationPanel.module.css'

type Props = {
  caseUuid: string
  value: string
  selectedAssetUuids: string[]
  disabled?: boolean
  pending?: boolean
  readOnlyReason?: string | null
  onChange: (value: string) => void
  onSelectedAssetsChange: (assetUuids: string[]) => void
  onSubmit: () => void
}

export function ConversationComposer({
  caseUuid,
  value,
  selectedAssetUuids,
  disabled = false,
  pending = false,
  readOnlyReason,
  onChange,
  onSelectedAssetsChange,
  onSubmit,
}: Props) {
  const labelId = useId()
  const helpId = useId()
  const busy = pending || disabled
  const canSend = value.trim().length > 0

  function handleKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault()
      if (!busy && canSend) {
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
        if (!busy && canSend) {
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

      <AttachmentPicker
        caseUuid={caseUuid}
        selectedAssetUuids={selectedAssetUuids}
        disabled={busy || Boolean(readOnlyReason)}
        onChange={onSelectedAssetsChange}
      />

      <div className={styles.composerActions}>
        <p className={styles.composerHint}>
          Enter sends · Shift+Enter for a new line
        </p>
        <button
          type="submit"
          className={styles.sendButton}
          disabled={busy || !canSend || Boolean(readOnlyReason)}
          aria-label="Send message"
        >
          {pending ? 'Sending…' : 'Send'}
        </button>
      </div>
    </form>
  )
}
