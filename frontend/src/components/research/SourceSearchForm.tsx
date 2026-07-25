import { useId } from 'react'
import type { ResearchSupportedFilter } from '../../api/types/research'
import styles from './SourcesResearch.module.css'

export type SourceSearchFormValues = {
  query: string
  sourceType: string
  sourceId: string
  limit: number
}

type Props = {
  values: SourceSearchFormValues
  sourceTypes: ResearchSupportedFilter[]
  pending: boolean
  onChange: (next: SourceSearchFormValues) => void
  onSubmit: () => void
  onClear: () => void
}

export function SourceSearchForm({
  values,
  sourceTypes,
  pending,
  onChange,
  onSubmit,
  onClear,
}: Props) {
  const formId = useId()
  const queryId = `${formId}-query`
  const typeId = `${formId}-type`
  const sourceIdField = `${formId}-source-id`
  const limitId = `${formId}-limit`

  return (
    <form
      className={styles.form}
      aria-labelledby={`${formId}-heading`}
      onSubmit={(event) => {
        event.preventDefault()
        if (!pending) {
          onSubmit()
        }
      }}
    >
      <h2 id={`${formId}-heading`} className={styles.heading}>
        Search controls
      </h2>
      <div className={styles.formGrid}>
        <div className={styles.field} style={{ gridColumn: '1 / -1' }}>
          <label className={styles.label} htmlFor={queryId}>
            Query
          </label>
          <input
            id={queryId}
            className={styles.input}
            name="query"
            type="search"
            value={values.query}
            onChange={(event) =>
              onChange({ ...values, query: event.target.value })
            }
            placeholder="Search indexed authority sources"
            autoComplete="off"
            disabled={pending}
          />
        </div>
        <div className={styles.field}>
          <label className={styles.label} htmlFor={typeId}>
            Source type
          </label>
          <select
            id={typeId}
            className={styles.select}
            name="sourceType"
            value={values.sourceType}
            onChange={(event) =>
              onChange({ ...values, sourceType: event.target.value })
            }
            disabled={pending}
          >
            <option value="">All supported types</option>
            {sourceTypes.map((item) => (
              <option key={item.value} value={item.value}>
                {item.label}
              </option>
            ))}
          </select>
        </div>
        <div className={styles.field}>
          <label className={styles.label} htmlFor={sourceIdField}>
            Document filter
          </label>
          <input
            id={sourceIdField}
            className={styles.input}
            name="sourceId"
            type="text"
            value={values.sourceId}
            onChange={(event) =>
              onChange({ ...values, sourceId: event.target.value })
            }
            placeholder="Canonical source id (optional)"
            autoComplete="off"
            disabled={pending}
          />
        </div>
        <div className={styles.field}>
          <label className={styles.label} htmlFor={limitId}>
            Result limit
          </label>
          <input
            id={limitId}
            className={styles.input}
            name="limit"
            type="number"
            min={1}
            max={24}
            value={values.limit}
            onChange={(event) =>
              onChange({
                ...values,
                limit: Number(event.target.value) || 12,
              })
            }
            disabled={pending}
          />
        </div>
      </div>
      <div className={styles.actions}>
        <button
          type="submit"
          className={styles.button}
          disabled={pending || values.query.trim().length === 0}
          aria-busy={pending}
        >
          {pending ? 'Searching…' : 'Search'}
        </button>
        <button
          type="button"
          className={styles.buttonSecondary}
          onClick={onClear}
          disabled={pending}
        >
          Clear
        </button>
      </div>
    </form>
  )
}
