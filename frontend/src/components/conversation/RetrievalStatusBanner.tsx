import type { RetrievalStatus } from '../../api/types/interactions'
import styles from './ConversationPanel.module.css'

type Props = {
  status: RetrievalStatus | null | undefined
  retrievalError?: boolean
  onRetry?: () => void
}

export function RetrievalStatusBanner({
  status,
  retrievalError,
  onRetry,
}: Props) {
  if (!status && !retrievalError) {
    return null
  }

  if (status === 'ok') {
    return (
      <p className={styles.statusBanner} role="status">
        Retrieval status: matched authorities available for this answer.
      </p>
    )
  }

  if (status === 'empty') {
    return (
      <p
        className={`${styles.statusBanner} ${styles.statusEmpty}`}
        role="status"
      >
        Retrieval status: empty — no matching authorities found in the indexed
        corpus.
      </p>
    )
  }

  if (status === 'failed' || retrievalError) {
    return (
      <div
        className={`${styles.statusBanner} ${styles.statusFailed}`}
        role="alert"
      >
        <p>
          Retrieval status: failed — sources could not be retrieved for this
          turn.
        </p>
        {onRetry ? (
          <button
            type="button"
            className={styles.retryButton}
            onClick={onRetry}
          >
            Retry
          </button>
        ) : null}
      </div>
    )
  }

  if (status === 'skipped') {
    return (
      <p
        className={`${styles.statusBanner} ${styles.statusSkipped}`}
        role="status"
      >
        Retrieval status: skipped — indexed retrieval was not run for this
        turn.
      </p>
    )
  }

  return (
    <p className={styles.statusBanner} role="status">
      Retrieval status: {String(status)}
    </p>
  )
}
