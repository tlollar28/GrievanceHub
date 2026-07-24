import styles from './PaginationControls.module.css'

type Props = {
  offset: number
  limit: number
  count: number
  total: number | null
  hasMore: boolean
  onPrevious: () => void
  onNext: () => void
  disabled?: boolean
}

export function PaginationControls({
  offset,
  count,
  total,
  hasMore,
  onPrevious,
  onNext,
  disabled = false,
}: Props) {
  const start = total === 0 || count === 0 ? 0 : offset + 1
  const end = offset + count
  const totalLabel = total == null ? '…' : String(total)

  return (
    <div className={styles.bar} role="navigation" aria-label="Pagination">
      <p className={styles.meta} aria-live="polite">
        Showing {start}–{end} of {totalLabel}
      </p>
      <div className={styles.actions}>
        <button
          type="button"
          className={styles.button}
          onClick={onPrevious}
          disabled={disabled || offset <= 0}
        >
          Previous
        </button>
        <button
          type="button"
          className={styles.button}
          onClick={onNext}
          disabled={disabled || !hasMore}
        >
          Next
        </button>
      </div>
    </div>
  )
}
