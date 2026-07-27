import type { AuthorityReportItem } from '../../api/types/reports'
import styles from './AnalysisPanel.module.css'

type Props = {
  heading: string
  items: AuthorityReportItem[] | undefined
  headingLevel?: 'h3' | 'h4'
}

function citationLabel(item: AuthorityReportItem): string | null {
  const citation = item.citation
  const parts: string[] = []
  const docType = citation?.document_type?.trim()
  const name = citation?.document_name?.trim()
  const section = item.article_or_section?.trim()
  if (docType) parts.push(docType)
  if (name) parts.push(name)
  if (section) parts.push(section)
  if (citation?.page != null) parts.push(`p. ${citation.page}`)
  return parts.length > 0 ? parts.join(' · ') : null
}

export function AuthoritySection({
  heading,
  items,
  headingLevel = 'h3',
}: Props) {
  if (!items || items.length === 0) {
    return null
  }

  const HeadingTag = headingLevel

  return (
    <section className={styles.block} aria-label={heading}>
      <p className={styles.kindLabel}>Citation reference · authority</p>
      <HeadingTag className={styles.blockHeading}>{heading}</HeadingTag>
      <div>
        {items.map((item, index) => {
          const role =
            item.role_title?.trim() ||
            item.role?.trim() ||
            'Authority'
          const quote = item.direct_quote?.trim()
          const why = item.why_relevant?.trim()
          const label = citationLabel(item)
          const key = `${heading}-${index}-${label ?? item.issue ?? 'item'}`

          return (
            <article key={key} className={styles.authorityItem}>
              <p className={styles.roleLabel}>{role}</p>
              {item.issue?.trim() ? <p>{item.issue.trim()}</p> : null}
              {why ? <p>{why}</p> : null}
              {quote ? (
                <blockquote className={styles.quote}>{quote}</blockquote>
              ) : null}
              {label ? (
                <p className={styles.citationRef}>
                  <span className={styles.kindLabel}>Citation reference</span>
                  {' — '}
                  {label}
                </p>
              ) : null}
              <p className={styles.exportHint}>
                Presence here does not mean this citation is controlling
                authority.
              </p>
            </article>
          )
        })}
      </div>
    </section>
  )
}
