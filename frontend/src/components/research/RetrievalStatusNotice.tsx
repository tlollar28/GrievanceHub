import type { ResearchUiStatus } from '../../api/types/research'
import styles from './SourcesResearch.module.css'

type Props = {
  status: ResearchUiStatus | null
  loading: boolean
  errorMessage?: string | null
  resultCount?: number
  totalMatched?: number
  query?: string
}

function statusCopy(
  status: ResearchUiStatus,
  resultCount: number,
  totalMatched: number,
  query: string,
): string {
  switch (status) {
    case 'ok':
      return `Found ${totalMatched} authority passage${totalMatched === 1 ? '' : 's'} for “${query}”. Showing ${resultCount}.`
    case 'partial':
      return `Partial retrieval for “${query}”: showing ${resultCount} of ${totalMatched} matched passages. Some sources were unavailable.`
    case 'empty':
      return `No matching authority passages were found for “${query}”.`
    case 'failed':
      return 'Authority retrieval failed. Try again, or narrow the query.'
    case 'skipped':
      return 'Authority retrieval was skipped for this query.'
    default:
      return 'Retrieval status unknown.'
  }
}

export function RetrievalStatusNotice({
  status,
  loading,
  errorMessage,
  resultCount = 0,
  totalMatched = 0,
  query = '',
}: Props) {
  if (loading) {
    return (
      <p className={styles.status} role="status" aria-live="polite">
        Searching the indexed authority corpus…
      </p>
    )
  }

  if (errorMessage) {
    return (
      <p className={styles.statusAlert} role="alert">
        {errorMessage}
      </p>
    )
  }

  if (!status) {
    return (
      <p className={styles.status} role="status">
        Enter a query and choose Search to inspect authority-corpus passages.
        Research does not change the current case.
      </p>
    )
  }

  const isFailure = status === 'failed'
  return (
    <p
      className={isFailure ? styles.statusAlert : styles.status}
      role={isFailure ? 'alert' : 'status'}
      aria-live="polite"
    >
      {statusCopy(status, resultCount, totalMatched, query)}
    </p>
  )
}
