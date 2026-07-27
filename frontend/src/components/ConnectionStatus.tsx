import { useQuery } from '@tanstack/react-query'
import { fetchHealth, isHealthyResponse } from '../api/health'
import styles from './ConnectionStatus.module.css'

export function ConnectionStatus() {
  const healthQuery = useQuery({
    queryKey: ['health'],
    queryFn: ({ signal }) => fetchHealth(signal),
    refetchInterval: 60_000,
  })

  let stateLabel = 'Checking'
  let stateClass = styles.checking

  if (healthQuery.isSuccess && isHealthyResponse(healthQuery.data)) {
    stateLabel = 'Connected'
    stateClass = styles.connected
  } else if (healthQuery.isError || (healthQuery.isSuccess && !isHealthyResponse(healthQuery.data))) {
    stateLabel = 'Unavailable'
    stateClass = styles.unavailable
  } else if (healthQuery.isFetching && !healthQuery.isSuccess) {
    stateLabel = 'Checking'
    stateClass = styles.checking
  }

  return (
    <div
      className={styles.root}
      role="status"
      aria-live="polite"
      aria-atomic="true"
    >
      <span className={`${styles.dot} ${stateClass}`} aria-hidden="true" />
      <span className={styles.label}>API: {stateLabel}</span>
      {stateLabel === 'Unavailable' ? (
        <button
          type="button"
          className={styles.retry}
          onClick={() => {
            void healthQuery.refetch()
          }}
        >
          Retry
        </button>
      ) : null}
    </div>
  )
}
