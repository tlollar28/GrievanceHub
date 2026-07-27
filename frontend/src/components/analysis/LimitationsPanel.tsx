import type { Limitations } from '../../api/types/reports'
import styles from './AnalysisPanel.module.css'

type Props = {
  limitations: Limitations | null | undefined
  researchDraftNotice?: string | null
  retrievalGaps?: Record<string, unknown> | null
}

function stringList(values: string[] | undefined): string[] {
  return (values ?? []).map((v) => v.trim()).filter((v) => v.length > 0)
}

export function LimitationsPanel({
  limitations,
  researchDraftNotice,
  retrievalGaps,
}: Props) {
  const missing = stringList(limitations?.missing_facts)
  const known = stringList(limitations?.known_facts)
  const caveats = stringList(limitations?.caveats)
  const notice = researchDraftNotice?.trim()
  const gaps = retrievalGaps ?? limitations?.retrieval_gaps
  const gapKeys =
    gaps && typeof gaps === 'object' ? Object.keys(gaps).filter(Boolean) : []

  if (
    !notice &&
    missing.length === 0 &&
    known.length === 0 &&
    caveats.length === 0 &&
    gapKeys.length === 0
  ) {
    return null
  }

  return (
    <section
      className={`${styles.block} ${styles.warningBlock}`}
      aria-label="Limitations and disclosures"
    >
      <p className={styles.kindLabel}>Warning or limitation</p>
      <h3 className={styles.blockHeading}>Limitations and disclosures</h3>
      {notice ? <p>{notice}</p> : null}
      {missing.length > 0 ? (
        <>
          <h4 className={styles.sectionHeading}>Missing facts</h4>
          <ul className={styles.list}>
            {missing.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
        </>
      ) : null}
      {known.length > 0 ? (
        <>
          <h4 className={styles.sectionHeading}>Known facts noted</h4>
          <ul className={styles.list}>
            {known.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
        </>
      ) : null}
      {caveats.length > 0 ? (
        <>
          <h4 className={styles.sectionHeading}>Caveats</h4>
          <ul className={styles.list}>
            {caveats.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
        </>
      ) : null}
      {gapKeys.length > 0 ? (
        <>
          <h4 className={styles.sectionHeading}>Retrieval gaps</h4>
          <ul className={styles.list}>
            {gapKeys.map((key) => (
              <li key={key}>{key}</li>
            ))}
          </ul>
        </>
      ) : null}
    </section>
  )
}
