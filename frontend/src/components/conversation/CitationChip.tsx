import type { InteractionCitation } from '../../api/types/interactions'
import styles from './ConversationPanel.module.css'

type Props = {
  citation: InteractionCitation
  index: number
  selected: boolean
  onSelect: () => void
  buttonRef?: (node: HTMLButtonElement | null) => void
}

function chipLabel(citation: InteractionCitation, index: number): string {
  const parts: string[] = []
  const docType = citation.document_type?.trim()
  const section = citation.article_or_section?.trim()
  const name = citation.document_name?.trim()
  if (docType) {
    parts.push(docType)
  }
  if (section) {
    parts.push(section)
  }
  if (parts.length === 0 && name) {
    parts.push(name)
  }
  if (parts.length === 0) {
    parts.push(`Citation ${index + 1}`)
  }
  return parts.join(' · ')
}

export function CitationChip({
  citation,
  index,
  selected,
  onSelect,
  buttonRef,
}: Props) {
  const grounded = citation.grounded !== false
  const ungrounded =
    !grounded || citation.grounding_provenance === 'ungrounded'
  const label = chipLabel(citation, index)

  return (
    <button
      ref={buttonRef}
      type="button"
      className={`${styles.chip} ${selected ? styles.chipSelected : ''} ${ungrounded ? styles.chipWarn : ''}`}
      aria-pressed={selected}
      aria-label={`${label}${ungrounded ? ' (ungrounded)' : ''}`}
      onClick={onSelect}
    >
      {label}
      {ungrounded ? ' · warning' : ''}
    </button>
  )
}
