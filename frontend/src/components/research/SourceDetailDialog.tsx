import { useEffect, useId, useRef, type RefObject } from 'react'
import { ApiError } from '../../api/client'
import type { ResearchSearchResultItem } from '../../api/types/research'
import { useResearchPassageQuery } from '../../features/research/useResearchPassageQuery'
import { formatRelevanceScore } from '../../features/research/sourceTypeLabels'
import styles from './SourcesResearch.module.css'

type Props = {
  selected: ResearchSearchResultItem | null
  selectedChunkId: number | null
  onClose: () => void
  returnFocusRef: RefObject<HTMLElement | null>
}

export function SourceDetailDialog({
  selected,
  selectedChunkId,
  onClose,
  returnFocusRef,
}: Props) {
  const titleId = useId()
  const closeRef = useRef<HTMLButtonElement>(null)
  const passageQuery = useResearchPassageQuery(selectedChunkId)
  const open = selectedChunkId != null

  useEffect(() => {
    if (!open) {
      return
    }
    const previous = document.activeElement as HTMLElement | null
    const restoreTarget = returnFocusRef.current
    closeRef.current?.focus()

    function onKeyDown(event: KeyboardEvent) {
      if (event.key === 'Escape') {
        event.preventDefault()
        onClose()
      }
    }
    document.addEventListener('keydown', onKeyDown)
    return () => {
      document.removeEventListener('keydown', onKeyDown)
      const restore = restoreTarget ?? previous
      restore?.focus?.()
    }
  }, [open, onClose, returnFocusRef])

  if (!open) {
    return null
  }

  const passage = passageQuery.data
  const title =
    passage?.source_title ?? selected?.source_title ?? 'Authority passage'
  const typeLabel =
    passage?.source_type_label ?? selected?.source_type_label ?? 'Source'
  const text =
    passage?.passage_text ?? selected?.passage_text ?? 'Loading passageâ€¦'
  const errorMessage =
    passageQuery.error instanceof ApiError
      ? passageQuery.error.message
      : passageQuery.isError
        ? 'Unable to load passage detail.'
        : null

  return (
    <div
      className={styles.dialogBackdrop}
      role="presentation"
      onMouseDown={(event) => {
        if (event.target === event.currentTarget) {
          onClose()
        }
      }}
    >
      <div
        className={styles.dialog}
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
      >
        <div className={styles.dialogHeader}>
          <h2 id={titleId} className={styles.dialogHeading}>
            {title}
          </h2>
          <button
            ref={closeRef}
            type="button"
            className={styles.closeButton}
            onClick={onClose}
          >
            Close
          </button>
        </div>
        <p className={styles.resultMeta}>
          Read-only authority passage. No source or case changes are made by
          opening this detail.
        </p>
        <dl className={styles.metaGrid}>
          <div className={styles.metaItem}>
            <dt>Source type</dt>
            <dd>
              {typeLabel}
              {passage?.source_type || selected?.source_type
                ? ` (${passage?.source_type ?? selected?.source_type})`
                : ''}
            </dd>
          </div>
          <div className={styles.metaItem}>
            <dt>Document id</dt>
            <dd>
              {passage?.canonical_source_id ??
                selected?.canonical_source_id ??
                'â€”'}
            </dd>
          </div>
          <div className={styles.metaItem}>
            <dt>Passage id</dt>
            <dd>{selectedChunkId}</dd>
          </div>
          <div className={styles.metaItem}>
            <dt>Page / section</dt>
            <dd>
              {passage?.page_number ?? selected?.page_number ?? 'â€”'}
              {passage?.section_label || selected?.section
                ? ` Â· ${passage?.section_label ?? selected?.section}`
                : ''}
            </dd>
          </div>
          {selected ? (
            <div className={styles.metaItem}>
              <dt>Relevance</dt>
              <dd>
                {formatRelevanceScore(selected.final_relevance_score)} (retrieval
                score, not legal weight)
              </dd>
            </div>
          ) : null}
          <div className={styles.metaItem}>
            <dt>Indexed</dt>
            <dd>
              {passage
                ? passage.is_indexed
                  ? 'Yes'
                  : 'No'
                : selected
                  ? 'Yes'
                  : 'â€”'}
            </dd>
          </div>
        </dl>
        {errorMessage ? (
          <p className={styles.statusAlert} role="alert">
            {errorMessage}
          </p>
        ) : null}
        {passageQuery.isFetching ? (
          <p className={styles.status} role="status" aria-busy="true">
            Loading full passageâ€¦
          </p>
        ) : null}
        <pre className={styles.passageBody}>{text}</pre>
      </div>
    </div>
  )
}
