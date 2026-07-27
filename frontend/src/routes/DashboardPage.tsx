import { useMemo } from 'react'
import { useSearchParams } from 'react-router-dom'
import { SavedCasesPanel } from '../components/cases/SavedCasesPanel'
import {
  DEFAULT_DASHBOARD_LIMIT,
  parseSavedCaseFilters,
  savedCaseFiltersToSearchParams,
} from '../features/cases/savedCaseFilters'
import type { ListSavedCasesParams } from '../api/types/savedCases'

export function DashboardPage() {
  const [searchParams, setSearchParams] = useSearchParams()

  const filters = useMemo(
    () =>
      parseSavedCaseFilters(searchParams, {
        limit: DEFAULT_DASHBOARD_LIMIT,
      }),
    [searchParams],
  )

  function onFiltersChange(next: ListSavedCasesParams) {
    setSearchParams(
      savedCaseFiltersToSearchParams(next, {
        limit: DEFAULT_DASHBOARD_LIMIT,
      }),
      { replace: true },
    )
  }

  return (
    <SavedCasesPanel
      headingId="dashboard-heading"
      title="Dashboard"
      description="Recent saved cases. Open or reopen a case to enter the workspace."
      filters={{
        ...filters,
        limit: filters.limit ?? DEFAULT_DASHBOARD_LIMIT,
      }}
      onFiltersChange={onFiltersChange}
      showPagination={false}
      compact
      viewAllHref="/cases"
    />
  )
}
