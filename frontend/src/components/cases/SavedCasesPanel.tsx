import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { ApiError } from '../../api/client'
import type {
  ListSavedCasesParams,
  SavedCaseSummary,
} from '../../api/types/savedCases'
import { useActivateCaseMutation } from '../../features/cases/useActivateCaseMutation'
import { useSavedCasesQuery } from '../../features/cases/useSavedCasesQuery'
import { PaginationControls } from './PaginationControls'
import { SavedCasesFilters } from './SavedCasesFilters'
import { SavedCasesTable } from './SavedCasesTable'
import styles from './SavedCasesPanel.module.css'

type Props = {
  filters: ListSavedCasesParams
  onFiltersChange?: (next: ListSavedCasesParams) => void
  showFilters?: boolean
  showPagination?: boolean
  compact?: boolean
  headingId: string
  title: string
  description?: string
  viewAllHref?: string
}

export function SavedCasesPanel({
  filters,
  onFiltersChange,
  showFilters = true,
  showPagination = true,
  compact = false,
  headingId,
  title,
  description,
  viewAllHref,
}: Props) {
  const navigate = useNavigate()
  const query = useSavedCasesQuery(filters)
  const activate = useActivateCaseMutation()
  const [activatingUuid, setActivatingUuid] = useState<string | null>(null)
  const [statusMessage, setStatusMessage] = useState<string | null>(null)
  const [pendingReopen, setPendingReopen] = useState<SavedCaseSummary | null>(
    null,
  )

  async function activateCase(
    summary: SavedCaseSummary,
    options: { forceReopen?: boolean } = {},
  ) {
    setStatusMessage(null)
    setPendingReopen(null)
    setActivatingUuid(summary.case_uuid)

    try {
      const result = await activate.mutateAsync({
        summary,
        forceReopen: options.forceReopen,
      })

      if (result.action_taken === 'closed_requires_reopen') {
        setPendingReopen(result.case)
        setStatusMessage(result.message)
        return
      }

      setStatusMessage(result.message)
      void navigate(`/cases/${result.case.case_uuid}`)
    } catch (error) {
      const message =
        error instanceof ApiError
          ? error.message
          : 'Unable to open this case.'
      setStatusMessage(message)
    } finally {
      setActivatingUuid(null)
    }
  }

  const cases = query.data?.cases ?? []
  const total = query.data?.total ?? null
  const limit = filters.limit ?? 25
  const offset = filters.offset ?? 0

  return (
    <section className={styles.panel} aria-labelledby={headingId}>
      <div className={styles.header}>
        <div>
          <h1 id={headingId}>{title}</h1>
          {description ? <p className={styles.description}>{description}</p> : null}
        </div>
        {viewAllHref ? (
          <Link className={styles.viewAll} to={viewAllHref}>
            View all cases
          </Link>
        ) : null}
      </div>

      {showFilters && onFiltersChange ? (
        <SavedCasesFilters
          filters={filters}
          onChange={onFiltersChange}
          idPrefix={compact ? 'dashboard' : 'cases'}
        />
      ) : null}

      <div
        className={styles.status}
        role="status"
        aria-live="polite"
        aria-atomic="true"
      >
        {statusMessage}
      </div>

      {pendingReopen ? (
        <div className={styles.confirm} role="region" aria-label="Reopen required">
          <p>
            Case{' '}
            <strong>{pendingReopen.title || pendingReopen.case_number}</strong>{' '}
            is {pendingReopen.workspace_status}. Reopen it to continue work?
          </p>
          <div className={styles.confirmActions}>
            <button
              type="button"
              className={styles.primaryButton}
              onClick={() =>
                void activateCase(pendingReopen, { forceReopen: true })
              }
              disabled={activatingUuid === pendingReopen.case_uuid}
            >
              Reopen case
            </button>
            <button
              type="button"
              className={styles.secondaryButton}
              onClick={() => {
                setPendingReopen(null)
                setStatusMessage(null)
              }}
            >
              Cancel
            </button>
          </div>
        </div>
      ) : null}

      {query.isLoading ? (
        <p className={styles.state} role="status">
          Loading saved cases…
        </p>
      ) : null}

      {query.isError ? (
        <div className={styles.error} role="alert">
          <p>
            {query.error instanceof ApiError
              ? query.error.message
              : 'Unable to load saved cases.'}
          </p>
          <button
            type="button"
            className={styles.secondaryButton}
            onClick={() => void query.refetch()}
          >
            Retry
          </button>
        </div>
      ) : null}

      {query.isSuccess && cases.length === 0 ? (
        <p className={styles.state}>
          No saved cases match the current filters.
        </p>
      ) : null}

      {query.isSuccess && cases.length > 0 ? (
        <SavedCasesTable
          cases={cases}
          activatingUuid={activatingUuid}
          onActivate={(summary, options) => {
            void activateCase(summary, options)
          }}
          compact={compact}
        />
      ) : null}

      {showPagination && query.isSuccess && onFiltersChange ? (
        <PaginationControls
          offset={offset}
          limit={limit}
          count={query.data?.count ?? 0}
          total={total}
          hasMore={query.data?.has_more ?? false}
          disabled={query.isFetching}
          onPrevious={() =>
            onFiltersChange({
              ...filters,
              offset: Math.max(0, offset - limit),
            })
          }
          onNext={() =>
            onFiltersChange({
              ...filters,
              offset: offset + limit,
            })
          }
        />
      ) : null}
    </section>
  )
}
