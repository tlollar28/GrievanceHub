import { ApiError } from '../../api/client'
import type { HistoryOrder } from '../../api/types/artifacts'
import { formatTimestamp } from '../../features/artifacts/artifactLibraryFilters'
import { useCaseTimelineQuery } from '../../features/cases/useCaseTimelineQuery'
import styles from './ArtifactsPanel.module.css'

type Props = {
  caseUuid: string
  order: HistoryOrder
  onOrderChange: (order: HistoryOrder) => void
}

export function CaseTimelinePanel({
  caseUuid,
  order,
  onOrderChange,
}: Props) {
  const timelineQuery = useCaseTimelineQuery(caseUuid, { order })
  const events = timelineQuery.data?.events ?? []

  return (
    <section className={styles.section} aria-labelledby="case-timeline-heading">
      <div className={styles.toolbar}>
        <h3 id="case-timeline-heading" className={styles.sectionHeading}>
          Case timeline
        </h3>
        <div className={styles.field}>
          <label className={styles.fieldLabel} htmlFor="timeline-order">
            Timeline order
          </label>
          <select
            id="timeline-order"
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
        Broader case history for review. Read-only — no workflow outcome
        controls.
      </p>

      {timelineQuery.isLoading && !timelineQuery.data ? (
        <p className={styles.skeleton} aria-busy="true" role="status">
          Loading timeline…
        </p>
      ) : null}

      {timelineQuery.isError && !timelineQuery.data ? (
        <div className={styles.errorBox} role="alert">
          <p>
            {timelineQuery.error instanceof ApiError
              ? timelineQuery.error.message
              : 'Unable to load case timeline.'}
          </p>
          <button
            type="button"
            className={styles.secondaryButton}
            onClick={() => {
              void timelineQuery.refetch()
            }}
          >
            Retry
          </button>
        </div>
      ) : null}

      {!timelineQuery.isLoading &&
      !timelineQuery.isError &&
      events.length === 0 ? (
        <p className={styles.empty} role="status">
          No timeline events for this case yet.
        </p>
      ) : null}

      {events.length > 0 ? (
        <ol className={styles.eventList} aria-label="Case timeline events">
          {events.map((event) => (
            <li key={event.event_id} className={styles.eventItem}>
              <div className={styles.metaRow}>
                <time dateTime={event.event_timestamp}>
                  {formatTimestamp(event.event_timestamp)}
                </time>
                <span className={styles.badge}>
                  {event.event_type.replaceAll('_', ' ')}
                </span>
                {event.step_type ? (
                  <span>{event.step_type.replaceAll('_', ' ')}</span>
                ) : null}
              </div>
              <p className={styles.itemTitle}>{event.title}</p>
              {event.details ? (
                <p className={styles.subhead}>{event.details}</p>
              ) : null}
              {event.references?.export_ref ||
              event.references?.report_version_number != null ||
              (event.references?.upload_refs?.length ?? 0) > 0 ? (
                <div className={styles.metaRow}>
                  {event.references?.report_version_number != null ? (
                    <span>
                      Report v{event.references.report_version_number}
                    </span>
                  ) : null}
                  {event.references?.export_ref ? (
                    <span>
                      Export ref {event.references.export_ref.slice(0, 8)}…
                    </span>
                  ) : null}
                  {(event.references?.upload_refs?.length ?? 0) > 0 ? (
                    <span>
                      Uploads: {event.references?.upload_refs?.length}
                    </span>
                  ) : null}
                </div>
              ) : null}
            </li>
          ))}
        </ol>
      ) : null}
    </section>
  )
}
