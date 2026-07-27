import type { CaseSavedArtifactSummary } from '../../api/types/artifacts'
import {
  artifactTypeLabel,
  formatTimestamp,
  pdfStatusLabel,
  shortArtifactId,
} from '../../features/artifacts/artifactLibraryFilters'
import styles from './ArtifactsPanel.module.css'

type Props = {
  artifacts: CaseSavedArtifactSummary[]
  selectedArtifactUuid: string | null
  compareLeft: string | null
  compareRight: string | null
  loading: boolean
  errorMessage: string | null
  onRetry: () => void
  onSelect: (artifactUuid: string) => void
  onToggleCompare: (artifactUuid: string) => void
}

export function ArtifactLibraryList({
  artifacts,
  selectedArtifactUuid,
  compareLeft,
  compareRight,
  loading,
  errorMessage,
  onRetry,
  onSelect,
  onToggleCompare,
}: Props) {
  if (loading) {
    return (
      <p className={styles.skeleton} aria-busy="true" role="status">
        Loading official artifacts…
      </p>
    )
  }

  if (errorMessage) {
    return (
      <div className={styles.errorBox} role="alert">
        <p>{errorMessage}</p>
        <button type="button" className={styles.secondaryButton} onClick={onRetry}>
          Retry
        </button>
      </div>
    )
  }

  if (artifacts.length === 0) {
    return (
      <p className={styles.empty} role="status">
        No official saved artifacts for this case yet. Save an analysis report
        or grievance form to populate the Artifact Library.
      </p>
    )
  }

  return (
    <ul className={styles.list} aria-label="Official artifacts">
      {artifacts.map((artifact) => {
        const selected = artifact.artifact_uuid === selectedArtifactUuid
        const inCompare =
          artifact.artifact_uuid === compareLeft ||
          artifact.artifact_uuid === compareRight
        const typeLabel = artifactTypeLabel(artifact.artifact_type)
        return (
          <li key={artifact.artifact_uuid}>
            <div
              className={`${styles.listItem} ${
                selected ? styles.listItemSelected : ''
              }`}
            >
              <input
                className={styles.compareCheck}
                type="checkbox"
                checked={inCompare}
                aria-label={`Select ${artifact.title || typeLabel} for comparison`}
                onChange={() => onToggleCompare(artifact.artifact_uuid)}
              />
              <button
                type="button"
                className={styles.listItemSelect}
                aria-current={selected ? 'true' : undefined}
                onClick={() => onSelect(artifact.artifact_uuid)}
              >
                <p className={styles.itemTitle}>
                  {artifact.title || typeLabel}
                </p>
                <div className={styles.metaRow}>
                  <span
                    className={`${styles.badge} ${
                      artifact.artifact_type === 'analysis_report'
                        ? styles.badgeAnalysis
                        : styles.badgeGrievance
                    }`}
                    aria-hidden="true"
                  >
                    {typeLabel}
                  </span>
                  <span className={styles.srOnly}>Type: {typeLabel}.</span>
                  <span>v{artifact.version_number}</span>
                  <span>{formatTimestamp(artifact.saved_at)}</span>
                  <span
                    className={
                      artifact.pdf_status === 'ready'
                        ? styles.statusReady
                        : artifact.pdf_status === 'failed'
                          ? styles.statusFailed
                          : styles.statusPending
                    }
                  >
                    {pdfStatusLabel(artifact.pdf_status)}
                  </span>
                  <span title={artifact.artifact_uuid}>
                    ID {shortArtifactId(artifact.artifact_uuid)}
                  </span>
                </div>
              </button>
            </div>
          </li>
        )
      })}
    </ul>
  )
}
