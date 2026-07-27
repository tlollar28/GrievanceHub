import type { FormEvent } from 'react'
import type {
  ListSavedCasesParams,
  SavedCaseOrder,
  SavedCaseStatusFilter,
  StepType,
} from '../../api/types/savedCases'
import styles from './SavedCasesFilters.module.css'

type Props = {
  filters: ListSavedCasesParams
  onChange: (next: ListSavedCasesParams) => void
  idPrefix?: string
  showSearch?: boolean
}

export function SavedCasesFilters({
  filters,
  onChange,
  idPrefix = 'cases',
  showSearch = true,
}: Props) {
  function update(partial: Partial<ListSavedCasesParams>) {
    onChange({
      ...filters,
      ...partial,
      offset: 0,
    })
  }

  function onSearchSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const form = new FormData(event.currentTarget)
    const search = String(form.get('search') ?? '').trim()
    update({ search: search.length > 0 ? search : null })
  }

  return (
    <div className={styles.filters}>
      {showSearch ? (
        <form className={styles.searchForm} onSubmit={onSearchSubmit}>
          <label className={styles.label} htmlFor={`${idPrefix}-search`}>
            Search
          </label>
          <div className={styles.searchRow}>
            <input
              id={`${idPrefix}-search`}
              name="search"
              type="search"
              className={styles.input}
              defaultValue={filters.search ?? ''}
              key={filters.search ?? ''}
              placeholder="UUID, title, or case number"
              autoComplete="off"
            />
            <button type="submit" className={styles.button}>
              Search
            </button>
          </div>
        </form>
      ) : null}

      <div className={styles.selectGrid}>
        <div className={styles.field}>
          <label className={styles.label} htmlFor={`${idPrefix}-status`}>
            Status
          </label>
          <select
            id={`${idPrefix}-status`}
            className={styles.select}
            value={filters.status ?? 'all'}
            onChange={(event) =>
              update({
                status: event.target.value as SavedCaseStatusFilter,
              })
            }
          >
            <option value="all">All</option>
            <option value="open">Open</option>
            <option value="closed">Closed</option>
            <option value="reopened">Reopened</option>
            <option value="appealed">Appealed</option>
            <option value="settled">Settled</option>
            <option value="archived">Archived</option>
          </select>
        </div>

        <div className={styles.field}>
          <label className={styles.label} htmlFor={`${idPrefix}-step`}>
            Step
          </label>
          <select
            id={`${idPrefix}-step`}
            className={styles.select}
            value={filters.step ?? ''}
            onChange={(event) =>
              update({
                step: (event.target.value || null) as StepType | null,
              })
            }
          >
            <option value="">All steps</option>
            <option value="step_1_initial">Step 1 — Initial</option>
            <option value="step_2_appeal">Step 2 — Appeal</option>
            <option value="step_3_appeal">Step 3 — Appeal</option>
          </select>
        </div>

        <div className={styles.field}>
          <label className={styles.label} htmlFor={`${idPrefix}-order`}>
            Order
          </label>
          <select
            id={`${idPrefix}-order`}
            className={styles.select}
            value={filters.order ?? 'newest_first'}
            onChange={(event) =>
              update({
                order: event.target.value as SavedCaseOrder,
              })
            }
          >
            <option value="newest_first">Newest first</option>
            <option value="oldest_first">Oldest first</option>
          </select>
        </div>
      </div>
    </div>
  )
}
