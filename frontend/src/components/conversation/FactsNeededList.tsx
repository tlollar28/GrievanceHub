import styles from './ConversationPanel.module.css'

type Props = {
  factsNeeded: string[]
}

function focusKnownFactsEditor() {
  const section = document.getElementById('known-facts-editor')
  if (!section) {
    return
  }
  if (typeof section.scrollIntoView === 'function') {
    section.scrollIntoView({ block: 'nearest', behavior: 'smooth' })
  }
  const focusable =
    section.querySelector<HTMLElement>(
      'input:not([disabled]), textarea:not([disabled]), button:not([disabled])',
    ) ?? section
  focusable.focus()
}

export function FactsNeededList({ factsNeeded }: Props) {
  if (factsNeeded.length === 0) {
    return null
  }

  return (
    <ul className={styles.factsList} aria-label="Facts needed">
      {factsNeeded.map((fact) => (
        <li key={fact} className={styles.factsItem}>
          <span>{fact}</span>
          <button
            type="button"
            className={styles.factsButton}
            onClick={focusKnownFactsEditor}
          >
            Open Known Facts editor
          </button>
        </li>
      ))}
    </ul>
  )
}
