import type { ResearchSearchResultItem } from '../../api/types/research'
import { formatRelevanceScore } from '../../features/research/sourceTypeLabels'
import styles from './SourcesResearch.module.css'

type Props = {
  item: ResearchSearchResultItem
  selected: boolean
  onSelect: (chunkId: number) => void
}

export function SourceResultItem({ item, selected, onSelect }: Props) {
  const locationParts = [
    item.article ? `Article ${item.article}` : null,
    item.section ? `Section ${item.section}` : null,
    item.page_number != null ? `Page ${item.page_number}` : null,
    `Chunk ${item.chunk_index}`,
  ].filter(Boolean)

  return (
    <li className={styles.resultItem}>
      <button
        type="button"
        className={styles.resultButton}
        aria-current={selected ? 'true' : undefined}
        onClick={() => onSelect(item.source_chunk_id)}
      >
        <div className={styles.resultTitleRow}>
          <h3 className={styles.resultTitle}>
            {item.rank}. {item.source_title}
          </h3>
          <p className={styles.resultMeta}>
            {formatRelevanceScore(item.final_relevance_score)}
          </p>
        </div>
        <p className={styles.resultMeta}>
          {item.source_type_label} ({item.source_type}) Â·{' '}
          {locationParts.join(' Â· ')}
        </p>
        <p className={styles.excerpt}>{item.excerpt || item.passage_text}</p>
        <p className={styles.resultMeta}>
          Provenance: {item.provenance}. Score reflects retrieval relevance, not
          legal weight.
        </p>
      </button>
    </li>
  )
}
