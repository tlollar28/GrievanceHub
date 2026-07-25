import { ApiError } from '../../api/client'
import type { HistoryOrder } from '../../api/types/artifacts'
import {
  artifactTypeLabel,
  formatTimestamp,
} from '../../features/artifacts/artifactLibraryFilters'
import { useCaseHistoryQuery } from '../../features/cases/useCaseHistoryQuery'
import styles from './ArtifactsPanel.module.css'

type Props = {
  caseUuid: string
  order: HistoryOrder
  onOrderChange: (order: HistoryOrder) => void
  onJumpToContext: (eventId: string) => void
  onOpenArtifact: (artifactUuid: string) => void
}

export function OfficialCaseRecord({
  caseUuid,
  order,
  onOrderChange,
  onJumpToContext,
  onOpenArtifact,
}: Props) {
  const historyQuery = useCaseHistoryQuery(caseUuid, {
    order,
    limit: 100,
  })
  const events = historyQuery.data?.events ?? []
  const label = historyQuery.data?.label || 'Official Case Record'

  return (
    <section className={styles.section} aria-labelledby="official-record-heading">
      <div className={styles.toolbar}>
        <h3 id="official-record-heading" className={styles.sectionHeading}>
          {label}
        </h3>
        <div className={styles.field}>
          <label className={styles.fieldLabel} htmlFor="history-order">
            History order
          </label>
          <select
            id="history-order"
            className={styles.select}
            value={order}
            onChange={(event) =>
              onOrderChange(event.target.value as HistoryOrder)
            }
          >
            <option value="newest_first">Newest first</option>
            <option value="oldest_first">Oldest first</option>
          </select>
        </div>
      </div>
      <p className={styles.subhead}>
        Steward-facing saved history for this case. This is not the internal
        domain-event log.
      </p>

      {historyQuery.isLoading && !historyQuery.data ? (
        <p className={styles.skeleton} aria-busy="true" role="status">
          Loading Official Case Record…
        </p>
      ) : null}

      {historyQuery.isError && !historyQuery.data ? (
        <div className={styles.errorBox} role="alert">
          <p>
            {historyQuery.error instanceof ApiError
              ? historyQuery.error.message
              : 'Unable to load Official Case Record.'}
          </p>
          <button
            type="button"
            className={styles.secondaryButton}
            onClick={() => {
              void historyQuery.refetch()
            }}
          >
            Retry
          </button>
        </div>
      ) : null}

      {!historyQuery.isLoading && !historyQuery.isError && events.length === 0 ? (
        <p className={styles.empty} role="status">
          No Official Case Record events for this case yet.
        </p>
      ) : null}

      {events.length > 0 ? (
        <ol className={styles.eventList} aria-label="Official Case Record events">
          {events.map((event) => (
            <li key={event.event_id} className={styles.eventItem}>
              <div className={styles.metaRow}>
                <time dateTime={event.event_timestamp}>
                  {formatTimestamp(event.event_timestamp)}
                </time>
                <span className={styles.badge}>
                  {event.display_label || event.event_type}
                </span>
                {event.record_class ? (
                  <span>{event.record_class.replaceAll('_', ' ')}</span>
                ) : null}
              </div>
              <p className={styles.itemTitle}>{event.title}</p>
              {event.details ? (
                <p className={styles.subhead}>{event.details}</p>
              ) : null}
              <div className={styles.metaRow}>
                <span>Type: {event.event_type}</span>
                {event.artifact_type ? (
                  <span>
                    Artifact: {artifactTypeLabel(event.artifact_type)}
                  </span>
                ) : null}
                {event.report_version_number != null ? (
                  <span>Report v{event.report_version_number}</span>
                ) : null}
              </div>
              <div className={styles.eventActions}>
                <button
                  type="button"
                  className={styles.secondaryButton}
                  onClick={() => onJumpToContext(event.event_id)}
                >
                  Jump to context
                </button>
                {event.artifact_uuid ? (
                  <button
                    type="button"
                    className={styles.linkButton}
                    onClick={() => onOpenArtifact(event.artifact_uuid as string)}
                  >
                    Open related artifact
                  </button>
                ) : null}
              </div>
            </li>
          ))}
        </ol>
      ) : null}
    </section>
  )
}
