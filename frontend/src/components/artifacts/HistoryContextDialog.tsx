import { useId } from 'react'
import { ApiError } from '../../api/client'
import {
  artifactTypeLabel,
  formatTimestamp,
} from '../../features/artifacts/artifactLibraryFilters'
import { useHistoryContextQuery } from '../../features/cases/useHistoryContextQuery'
import { useModalDialogFocus } from '../useModalDialogFocus'
import styles from './ArtifactsPanel.module.css'

type Props = {
  caseUuid: string
  eventId: string | null
  onClose: () => void
}

function asRecord(value: unknown): Record<string, unknown> | null {
  if (value && typeof value === 'object' && !Array.isArray(value)) {
    return value as Record<string, unknown>
  }
  return null
}

function textValue(value: unknown): string {
  if (value == null) return '—'
  if (typeof value === 'string') return value
  if (typeof value === 'number' || typeof value === 'boolean') {
    return String(value)
  }
  return '—'
}

export function HistoryContextDialog({
  caseUuid,
  eventId,
  onClose,
}: Props) {
  const titleId = useId()
  const open = Boolean(eventId)
  const dialogRef = useModalDialogFocus({ open, onClose })
  const contextQuery = useHistoryContextQuery(
    caseUuid,
    eventId,
    { conversation_window: 8 },
    open,
  )

  if (!open || !eventId) return null

  const data = contextQuery.data
  const eventDetails = asRecord(data?.event_details)
  const artifact = asRecord(data?.related_artifact)
  const messages = data?.related_conversation?.messages ?? []
  const mutates = data?.mutates_current_memory === true

  return (
    <div
      className={styles.dialogBackdrop}
      role="presentation"
      onMouseDown={(event) => {
        if (event.target === event.currentTarget) onClose()
      }}
    >
      <div
        ref={dialogRef}
        className={styles.dialog}
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        tabIndex={-1}
      >
        <div className={styles.dialogHeader}>
          <h2 id={titleId} className={styles.dialogTitle}>
            Jump to context
          </h2>
          <button
            type="button"
            className={styles.secondaryButton}
            onClick={onClose}
          >
            Close
          </button>
        </div>

        <p className={styles.statusText} role="status">
          Read-only historical context for this case. This view does not create
          messages, artifacts, analysis, or grievances
          {mutates ? '' : ', and does not mutate Case Memory'}.
        </p>

        {contextQuery.isLoading && !data ? (
          <p className={styles.skeleton} aria-busy="true" role="status">
            Loading context…
          </p>
        ) : null}

        {contextQuery.isError && !data ? (
          <div className={styles.errorBox} role="alert">
            <p>
              {contextQuery.error instanceof ApiError
                ? contextQuery.error.message
                : 'Unable to load history context.'}
            </p>
            <button
              type="button"
              className={styles.secondaryButton}
              onClick={() => void contextQuery.refetch()}
            >
              Retry
            </button>
          </div>
        ) : null}

        {data ? (
          <div className={styles.stack}>
            <dl className={styles.dl}>
              <dt>Event</dt>
              <dd>{textValue(eventDetails?.title ?? eventId)}</dd>
              <dt>Event type</dt>
              <dd>{textValue(eventDetails?.event_type)}</dd>
              <dt>Timestamp</dt>
              <dd>
                {formatTimestamp(
                  typeof eventDetails?.event_timestamp === 'string'
                    ? eventDetails.event_timestamp
                    : null,
                )}
              </dd>
              <dt>Record class</dt>
              <dd>{textValue(data.record_class)}</dd>
            </dl>

            {eventDetails?.details ? (
              <p className={styles.subhead}>{textValue(eventDetails.details)}</p>
            ) : null}

            {artifact ? (
              <section>
                <h3 className={styles.sectionHeading}>Related artifact</h3>
                <dl className={styles.dl}>
                  <dt>Title</dt>
                  <dd>{textValue(artifact.title)}</dd>
                  <dt>Type</dt>
                  <dd>
                    {artifactTypeLabel(textValue(artifact.artifact_type))}
                  </dd>
                  <dt>Version</dt>
                  <dd>{textValue(artifact.version_number)}</dd>
                </dl>
              </section>
            ) : null}

            {data.related_workflow_state ? (
              <section>
                <h3 className={styles.sectionHeading}>Related workflow</h3>
                <dl className={styles.dl}>
                  {Object.entries(data.related_workflow_state).map(
                    ([key, value]) => (
                      <div key={key} style={{ display: 'contents' }}>
                        <dt>{key.replaceAll('_', ' ')}</dt>
                        <dd>{textValue(value)}</dd>
                      </div>
                    ),
                  )}
                </dl>
              </section>
            ) : null}

            <section>
              <h3 className={styles.sectionHeading}>Nearby messages</h3>
              {messages.length === 0 ? (
                <p className={styles.empty} role="status">
                  No nearby conversation messages for this event.
                </p>
              ) : (
                <ul className={styles.messageList} aria-label="Nearby messages">
                  {messages.map((message, index) => {
                    const row = asRecord(message)
                    const role = textValue(row?.role)
                    const content = textValue(row?.content)
                    const id = row?.id
                    return (
                      <li
                        key={typeof id === 'number' || typeof id === 'string' ? String(id) : index}
                        className={styles.messageItem}
                      >
                        <div className={styles.messageRole}>{role}</div>
                        <div>{content}</div>
                      </li>
                    )
                  })}
                </ul>
              )}
            </section>

            {(data.previous_event || data.next_event) ? (
              <section>
                <h3 className={styles.sectionHeading}>Event position</h3>
                <dl className={styles.dl}>
                  <dt>Previous</dt>
                  <dd>
                    {textValue(asRecord(data.previous_event)?.title) || '—'}
                  </dd>
                  <dt>Next</dt>
                  <dd>
                    {textValue(asRecord(data.next_event)?.title) || '—'}
                  </dd>
                </dl>
              </section>
            ) : null}

            {(data.unavailable_fields?.length ?? 0) > 0 ? (
              <p className={styles.warningBox} role="status">
                Unavailable fields:{' '}
                {data.unavailable_fields?.join(', ')}
              </p>
            ) : null}
          </div>
        ) : null}
      </div>
    </div>
  )
}
