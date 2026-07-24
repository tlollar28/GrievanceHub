import { useMemo } from 'react'
import { useSearchParams } from 'react-router-dom'
import { SavedCasesPanel } from '../components/cases/SavedCasesPanel'
import {
  DEFAULT_CASES_LIMIT,
  parseSavedCaseFilters,
  savedCaseFiltersToSearchParams,
} from '../features/cases/savedCaseFilters'
import type { ListSavedCasesParams } from '../api/types/savedCases'

export function CasesPage() {
  const [searchParams, setSearchParams] = useSearchParams()

  const filters = useMemo(
    () =>
      parseSavedCaseFilters(searchParams, {
        limit: DEFAULT_CASES_LIMIT,
      }),
    [searchParams],
  )

  function onFiltersChange(next: ListSavedCasesParams) {
    setSearchParams(
      savedCaseFiltersToSearchParams(next, {
        limit: DEFAULT_CASES_LIMIT,
      }),
      { replace: true },
    )
  }

  return (
    <SavedCasesPanel
      headingId="cases-heading"
      title="Cases"
      description="Full Saved Cases list. Filters are reflected in the URL."
      filters={{
        ...filters,
        limit: filters.limit ?? DEFAULT_CASES_LIMIT,
      }}
      onFiltersChange={onFiltersChange}
      showPagination
    />
  )
}
