import type { CitationValidation } from '../../api/types/reports'
import styles from './AnalysisPanel.module.css'

type Props = {
  validation: CitationValidation | null | undefined
}

export function CitationValidationSummary({ validation }: Props) {
  if (!validation) {
    return null
  }

  const status = validation.status?.trim()
  const notes = validation.notes?.filter((n) => n.trim().length > 0) ?? []

  return (
    <section
      className={`${styles.block} ${styles.warningBlock}`}
      aria-label="Citation validation"
    >
      <p className={styles.kindLabel}>Warning or limitation</p>
      <h3 className={styles.blockHeading}>Citation validation</h3>
      {status ? <p>Status: {status}</p> : null}
      {typeof validation.evidence_items_checked === 'number' ? (
        <p>Evidence items checked: {validation.evidence_items_checked}</p>
      ) : null}
      {typeof validation.direct_quotes_found === 'number' ? (
        <p>Direct quotes found: {validation.direct_quotes_found}</p>
      ) : null}
      {notes.length > 0 ? (
        <ul className={styles.list}>
          {notes.map((note) => (
            <li key={note}>{note}</li>
          ))}
        </ul>
      ) : null}
    </section>
  )
}
