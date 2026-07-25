import type { InteractionCitation } from '../../api/types/interactions'
import styles from './ConversationPanel.module.css'

type Props = {
  citation: InteractionCitation
}

function optionalText(value: unknown): string | null {
  if (typeof value !== 'string') {
    return null
  }
  const trimmed = value.trim()
  return trimmed.length > 0 ? trimmed : null
}

export function CitationDetail({ citation }: Props) {
  const documentType = optionalText(citation.document_type)
  const documentName = optionalText(citation.document_name)
  const section = optionalText(citation.article_or_section)
  const quote = optionalText(citation.quote)
  const page =
    typeof citation.page === 'number' && Number.isFinite(citation.page)
      ? citation.page
      : null
  const grounded = citation.grounded !== false
  const provenance =
    optionalText(citation.grounding_provenance) ?? 'unknown'
  const ungrounded =
    !grounded || citation.grounding_provenance === 'ungrounded'

  return (
    <div className={styles.detailBlock}>
      {documentName ? (
        <div className={styles.detailBlock}>
          <p className={styles.detailLabel}>Document</p>
          <p className={styles.detailValue}>{documentName}</p>
        </div>
      ) : null}
      {documentType ? (
        <div className={styles.detailBlock}>
          <p className={styles.detailLabel}>Document type</p>
          <p className={styles.detailValue}>{documentType}</p>
        </div>
      ) : null}
      {section ? (
        <div className={styles.detailBlock}>
          <p className={styles.detailLabel}>Article or section</p>
          <p className={styles.detailValue}>{section}</p>
        </div>
      ) : null}
      {page !== null ? (
        <div className={styles.detailBlock}>
          <p className={styles.detailLabel}>Page</p>
          <p className={styles.detailValue}>{page}</p>
        </div>
      ) : null}
      <div className={styles.detailBlock}>
        <p className={styles.detailLabel}>Grounding</p>
        <p className={styles.detailValue}>
          {grounded ? 'Grounded' : 'Not grounded'} · {provenance}
        </p>
      </div>
      {ungrounded ? (
        <p className={styles.groundingWarn} role="status">
          This citation is not grounded in a retrieved passage. It is not
          controlling authority.
        </p>
      ) : null}
      {quote ? (
        <div className={styles.detailBlock}>
          <p className={styles.detailLabel}>Source excerpt</p>
          <blockquote className={styles.sourceQuote}>{quote}</blockquote>
        </div>
      ) : null}
    </div>
  )
}
