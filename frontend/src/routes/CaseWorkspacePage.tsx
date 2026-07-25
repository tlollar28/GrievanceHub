import { useEffect, useRef } from 'react'
import { Link, useParams } from 'react-router-dom'
import { ApiError } from '../api/client'
import { CaseWorkspaceShell } from '../components/workspace/CaseWorkspaceShell'
import { useCaseWorkspaceQuery } from '../features/cases/useCaseWorkspaceQuery'
import styles from './CaseWorkspacePage.module.css'

/**
 * Durable workspace restoration for /cases/:caseUuid.
 * Uses cached open/reopen payload when present, then authoritative
 * GET /cases/{uuid}/workspace.
 */
export function CaseWorkspacePage() {
  const { caseUuid = '' } = useParams()
  const query = useCaseWorkspaceQuery(caseUuid)
  const headingRef = useRef<HTMLHeadingElement>(null)

  useEffect(() => {
    if (!caseUuid) {
      return
    }
    const heading =
      headingRef.current ??
      document.querySelector<HTMLElement>('#case-workspace-heading, h1')
    heading?.focus()
  }, [caseUuid, query.dataUpdatedAt, query.isError, query.isLoading])

  if (!caseUuid) {
    return (
      <section className={styles.statePage} aria-labelledby="workspace-missing">
        <h1 id="workspace-missing" tabIndex={-1} ref={headingRef}>
          Case not specified
        </h1>
        <p>
          <Link to="/cases">Return to Cases</Link>
        </p>
      </section>
    )
  }

  if (query.isLoading && !query.data) {
    return (
      <section
        className={styles.statePage}
        aria-labelledby="workspace-loading"
        aria-busy="true"
      >
        <h1 id="workspace-loading" tabIndex={-1} ref={headingRef}>
          Restoring case workspace…
        </h1>
        <p role="status">Loading case {caseUuid}</p>
      </section>
    )
  }

  if (query.isError && !query.data) {
    const isNotFound =
      query.error instanceof ApiError && query.error.status === 404
    const message =
      query.error instanceof ApiError
        ? query.error.message
        : 'Unable to load this case workspace.'

    return (
      <section
        className={styles.statePage}
        aria-labelledby="workspace-error"
      >
        <h1 id="workspace-error" tabIndex={-1} ref={headingRef}>
          {isNotFound ? 'Case not found' : 'Case unavailable'}
        </h1>
        <p className={styles.alert} role="alert">
          {message}
        </p>
        <div className={styles.actions}>
          {!isNotFound ? (
            <button
              type="button"
              className={styles.retryButton}
              onClick={() => {
                void query.refetch()
              }}
            >
              Retry
            </button>
          ) : null}
          <Link to="/cases">Return to Cases</Link>
        </div>
      </section>
    )
  }

  const workspace = query.data
  if (!workspace) {
    return (
      <section className={styles.statePage} aria-labelledby="workspace-empty">
        <h1 id="workspace-empty" tabIndex={-1} ref={headingRef}>
          Case unavailable
        </h1>
        <p role="alert">No workspace data was returned for this case.</p>
        <Link to="/cases">Return to Cases</Link>
      </section>
    )
  }

  return (
    <div aria-busy={query.isFetching || undefined}>
      <CaseWorkspaceShell workspace={workspace} />
    </div>
  )
}
