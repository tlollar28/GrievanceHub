import { useEffect, useId, useState } from 'react'
import { ApiError } from '../../api/client'
import type { KnownFacts } from '../../api/types/cases'
import {
  createEmptyFactRow,
  factsToRows,
  rowsToFacts,
  type FactRow,
} from '../../features/cases/knownFactsForm'
import { useUpdateFactsMutation } from '../../features/cases/useUpdateFactsMutation'
import styles from './KnownFactsEditor.module.css'

type Props = {
  caseUuid: string
  knownFacts: KnownFacts | null | undefined
  readOnly?: boolean
}

function rowsEqual(a: FactRow[], b: FactRow[]): boolean {
  if (a.length !== b.length) {
    return false
  }
  return a.every(
    (row, index) =>
      row.key === b[index]?.key && row.value === b[index]?.value,
  )
}

export function KnownFactsEditor({
  caseUuid,
  knownFacts,
  readOnly = false,
}: Props) {
  const headingId = useId()
  const mutation = useUpdateFactsMutation()
  const [baseline, setBaseline] = useState<FactRow[]>(() =>
    factsToRows(knownFacts),
  )
  const [rows, setRows] = useState<FactRow[]>(() => factsToRows(knownFacts))
  const [successMessage, setSuccessMessage] = useState<string | null>(null)
  const [localError, setLocalError] = useState<string | null>(null)

  const factsSyncKey = JSON.stringify(knownFacts ?? {})

  useEffect(() => {
    const parsed = JSON.parse(factsSyncKey) as KnownFacts
    const next = factsToRows(
      Object.keys(parsed).length > 0 ? parsed : null,
    )
    setBaseline(next)
    setRows(next)
  }, [factsSyncKey])

  const dirty = !rowsEqual(rows, baseline)
  const busy = mutation.isPending

  function updateRow(id: string, patch: Partial<FactRow>) {
    setRows((current) =>
      current.map((row) => (row.id === id ? { ...row, ...patch } : row)),
    )
    setSuccessMessage(null)
    setLocalError(null)
  }

  function handleAddRow() {
    setRows((current) => [...current, createEmptyFactRow()])
    setSuccessMessage(null)
  }

  function handleRemoveRow(id: string) {
    setRows((current) => current.filter((row) => row.id !== id))
    setSuccessMessage(null)
  }

  function handleCancel() {
    setRows(baseline.map((row) => ({ ...row })))
    setLocalError(null)
    setSuccessMessage(null)
    mutation.reset()
  }

  function handleSave() {
    const facts = rowsToFacts(rows)
    const duplicateKeys = new Set<string>()
    const seen = new Set<string>()
    for (const row of rows) {
      const key = row.key.trim()
      if (!key) {
        continue
      }
      if (seen.has(key)) {
        duplicateKeys.add(key)
      }
      seen.add(key)
    }
    if (duplicateKeys.size > 0) {
      setLocalError('Fact keys must be unique.')
      return
    }

    setLocalError(null)
    setSuccessMessage(null)
    mutation.mutate(
      { caseUuid, knownFacts: facts },
      {
        onSuccess: () => {
          setSuccessMessage('Known facts saved.')
        },
      },
    )
  }

  const apiError =
    mutation.error instanceof ApiError
      ? mutation.error.message
      : mutation.error
        ? 'Unable to save known facts.'
        : null

  return (
    <section
      id="known-facts-editor"
      className={styles.section}
      aria-labelledby={headingId}
      aria-busy={busy || undefined}
      tabIndex={-1}
    >
      <h3 id={headingId} className={styles.heading}>
        Known facts
      </h3>
      <p className={styles.help}>
        Steward-maintained facts stored on the case. Saving replaces the full
        known-facts object on the server.
      </p>

      {rows.length === 0 ? (
        <p className={styles.empty}>No known facts recorded yet.</p>
      ) : null}

      <ul className={styles.rows}>
        {rows.map((row, index) => (
          <li key={row.id} className={styles.row}>
            <div className={styles.field}>
              <label htmlFor={`${row.id}-key`}>Key</label>
              <input
                id={`${row.id}-key`}
                name={`fact-key-${index}`}
                value={row.key}
                onChange={(event) =>
                  updateRow(row.id, { key: event.target.value })
                }
                disabled={readOnly || busy}
                autoComplete="off"
              />
            </div>
            <div className={styles.field}>
              <label htmlFor={`${row.id}-value`}>Value</label>
              <textarea
                id={`${row.id}-value`}
                name={`fact-value-${index}`}
                value={row.value}
                rows={2}
                onChange={(event) =>
                  updateRow(row.id, { value: event.target.value })
                }
                disabled={readOnly || busy}
              />
            </div>
            {!readOnly ? (
              <button
                type="button"
                className={styles.removeButton}
                onClick={() => handleRemoveRow(row.id)}
                disabled={busy}
                aria-label={`Remove fact ${row.key || index + 1}`}
              >
                Remove
              </button>
            ) : null}
          </li>
        ))}
      </ul>

      {!readOnly ? (
        <div className={styles.actions}>
          <button
            type="button"
            className={styles.addButton}
            onClick={handleAddRow}
            disabled={busy}
          >
            Add fact
          </button>
          <button
            type="button"
            className={styles.saveButton}
            onClick={handleSave}
            disabled={busy || !dirty}
          >
            {busy ? 'Saving…' : 'Save facts'}
          </button>
          <button
            type="button"
            className={styles.cancelButton}
            onClick={handleCancel}
            disabled={busy || !dirty}
          >
            Cancel
          </button>
          {dirty ? (
            <span className={styles.dirty} role="status">
              Unsaved changes
            </span>
          ) : null}
        </div>
      ) : null}

      {localError || apiError ? (
        <p className={styles.error} role="alert">
          {localError ?? apiError}
        </p>
      ) : null}
      {successMessage ? (
        <p className={styles.success} role="status">
          {successMessage}
        </p>
      ) : null}
    </section>
  )
}
