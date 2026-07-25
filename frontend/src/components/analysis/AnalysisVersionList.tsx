import type { AnalysisVersionSummary } from '../../api/types/reports'
import styles from './AnalysisPanel.module.css'

type Props = {
  versions: AnalysisVersionSummary[]
  selectedVersion: number | null
  loading: boolean
  errorMessage: string | null
  onRetry: () => void
  onSelect: (versionNumber: number) => void
}

function formatWhen(value: string | null | undefined): string {
  if (!value) return 'Unknown time'
  const parsed = Date.parse(value)
  if (Number.isNaN(parsed)) return value
  return new Date(parsed).toLocaleString()
}

function summaryTitle(version: AnalysisVersionSummary): string | null {
  const summary = version.report_summary
  if (!summary || typeof summary !== 'object') return null
  const record = summary as Record<string, unknown>
  const title = record.title
  return typeof title === 'string' && title.trim() ? title.trim() : null
}

export function AnalysisVersionList({
  versions,
  selectedVersion,
  loading,
  errorMessage,
  onRetry,
  onSelect,
}: Props) {
  if (loading) {
    return (
      <p className={styles.skeleton} aria-busy="true">
        Loading saved analysis versions…
      </p>
    )
  }

  if (errorMessage) {
    return (
      <div className={styles.errorBox} role="alert">
        <p>{errorMessage}</p>
        <button type="button" className={styles.retryButton} onClick={onRetry}>
          Retry
        </button>
      </div>
    )
  }

  if (versions.length === 0) {
    return (
      <p className={styles.empty}>
        No saved analysis versions yet. Generate a temporary preview, then Save
        to create the first official version.
      </p>
    )
  }

  const sorted = [...versions].sort(
    (a, b) => b.version_number - a.version_number,
  )

  return (
    <ul className={styles.versionList} aria-label="Saved analysis versions">
      {sorted.map((version) => {
        const selected = selectedVersion === version.version_number
        const title = summaryTitle(version)
        return (
          <li key={version.id ?? version.version_number}>
            <button
              type="button"
              className={`${styles.versionButton}${selected ? ` ${styles.versionButtonSelected}` : ''}`}
              aria-pressed={selected}
              aria-label={`Saved analysis version ${version.version_number}${title ? `, ${title}` : ''}`}
              onClick={() => onSelect(version.version_number)}
            >
              <span>
                Version {version.version_number}{' '}
                <span className={styles.officialBadge}>Official</span>
              </span>
              {title ? <span>{title}</span> : null}
              <span className={styles.versionMeta}>
                {formatWhen(version.created_at)}
              </span>
            </button>
          </li>
        )
      })}
    </ul>
  )
}
