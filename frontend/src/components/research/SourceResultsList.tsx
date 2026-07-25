import type { ResearchSearchResultItem } from '../../api/types/research'
import { SourceResultItem } from './SourceResultItem'
import styles from './SourcesResearch.module.css'

type Props = {
  results: ResearchSearchResultItem[]
  selectedChunkId: number | null
  onSelect: (chunkId: number) => void
  offset: number
  limit: number
  totalMatched: number
  onPrevPage: () => void
  onNextPage: () => void
}

export function SourceResultsList({
  results,
  selectedChunkId,
  onSelect,
  offset,
  limit,
  totalMatched,
  onPrevPage,
  onNextPage,
}: Props) {
  if (results.length === 0) {
    return null
  }

  const canPrev = offset > 0
  const canNext = offset + limit < totalMatched

  return (
    <section aria-labelledby="research-results-heading">
      <h2 id="research-results-heading" className={styles.heading}>
        Authority results
      </h2>
      <ul className={styles.results}>
        {results.map((item) => (
          <SourceResultItem
            key={`${item.source_document_id}-${item.source_chunk_id}`}
            item={item}
            selected={selectedChunkId === item.source_chunk_id}
            onSelect={onSelect}
          />
        ))}
      </ul>
      {(canPrev || canNext) && (
        <div className={styles.pagination}>
          <button
            type="button"
            className={styles.buttonSecondary}
            onClick={onPrevPage}
            disabled={!canPrev}
          >
            Previous
          </button>
          <button
            type="button"
            className={styles.buttonSecondary}
            onClick={onNextPage}
            disabled={!canNext}
          >
            Next
          </button>
          <span className={styles.resultMeta}>
            Offset {offset} Â· limit {limit} Â· matched {totalMatched}
          </span>
        </div>
      )}
    </section>
  )
}
