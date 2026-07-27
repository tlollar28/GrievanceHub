import type { CaseSavedArtifactSummary } from '../../api/types/grievances'
import {
  stepTypeLabel,
  templateDisplayName,
} from '../../features/grievance/templateFields'
import styles from './GrievancePanel.module.css'

type Props = {
  artifacts: CaseSavedArtifactSummary[]
  selectedArtifactUuid: string | null
  loading: boolean
  errorMessage: string | null
  onRetry: () => void
  onSelect: (artifactUuid: string) => void
}

function formatSavedAt(value: string | undefined): string {
  if (!value) return '—'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  return date.toLocaleString()
}

export function GrievanceArtifactList({
  artifacts,
  selectedArtifactUuid,
  loading,
  errorMessage,
  onRetry,
  onSelect,
}: Props) {
  if (loading) {
    return (
      <p className={styles.skeleton} aria-busy="true">
        Loading saved grievances…
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

  if (artifacts.length === 0) {
    return (
      <p className={styles.empty}>
        No saved Step 1 or Step 2 grievance artifacts yet. Generate a temporary
        draft, then Save to create the first official grievance.
      </p>
    )
  }

  return (
    <ul className={styles.versionList} aria-label="Saved grievance artifacts">
      {artifacts.map((artifact) => {
        const selected = artifact.artifact_uuid === selectedArtifactUuid
        const templateLabel = artifact.template_id
          ? templateDisplayName(artifact.template_id)
          : 'Grievance form'
        return (
          <li key={artifact.artifact_uuid}>
            <button
              type="button"
              className={`${styles.artifactButton}${selected ? ` ${styles.artifactButtonSelected}` : ''}`}
              aria-pressed={selected}
              aria-label={`${templateLabel}, version ${artifact.version_number}, PDF ${artifact.pdf_status ?? 'unknown'}`}
              onClick={() => onSelect(artifact.artifact_uuid)}
            >
              <span>
                {artifact.title || templateLabel} · v{artifact.version_number}
              </span>
              <span className={styles.versionMeta}>
                {artifact.template_id
                  ? templateDisplayName(artifact.template_id)
                  : 'Unknown template'}
                {artifact.grievance_step
                  ? ` · ${stepTypeLabel(artifact.grievance_step)}`
                  : ''}
              </span>
              <span className={styles.versionMeta}>
                Saved {formatSavedAt(artifact.saved_at)} · PDF:{' '}
                {artifact.pdf_status ?? 'pending'}
                {artifact.is_latest_official ? ' · Official' : ''}
              </span>
            </button>
          </li>
        )
      })}
    </ul>
  )
}
