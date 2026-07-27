import { useEffect, useId, useRef, useState } from 'react'
import type { InteractionCitation } from '../../api/types/interactions'
import { CitationDetail } from './CitationDetail'
import styles from './ConversationPanel.module.css'

type Props = {
  citation: InteractionCitation | null
  onClose?: () => void
}

export function CitationPanel({ citation, onClose }: Props) {
  const headingId = useId()
  const panelRef = useRef<HTMLElement>(null)
  const [collapsed, setCollapsed] = useState(false)

  useEffect(() => {
    if (!citation) {
      return
    }
    setCollapsed(false)
    panelRef.current?.focus()
  }, [citation])

  return (
    <aside
      ref={panelRef}
      className={`${styles.researchPanel} ${collapsed ? styles.researchPanelCollapsed : ''}`}
      aria-labelledby={headingId}
      tabIndex={-1}
    >
      <div className={styles.researchHeader}>
        <h2 id={headingId} className={styles.researchHeading}>
          Research
        </h2>
        <button
          type="button"
          className={styles.collapseButton}
          aria-expanded={!collapsed}
          onClick={() => setCollapsed((value) => !value)}
        >
          {collapsed ? 'Expand research panel' : 'Collapse research panel'}
        </button>
      </div>
      {!collapsed ? (
        <div className={styles.researchBody}>
          {citation ? (
            <>
              <CitationDetail citation={citation} />
              {onClose ? (
                <button
                  type="button"
                  className={styles.collapseButton}
                  onClick={onClose}
                >
                  Clear selection
                </button>
              ) : null}
            </>
          ) : (
            <p className={styles.researchEmpty}>
              Select a citation chip on an assistant answer to inspect the
              source excerpt and grounding state. No citation is selected.
            </p>
          )}
        </div>
      ) : null}
    </aside>
  )
}
