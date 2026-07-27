import { ApiError } from '../../api/client'
import type {
  ArtifactCompareResponse,
  CaseSavedArtifactSummary,
} from '../../api/types/artifacts'
import {
  artifactTypeLabel,
  canCompareArtifacts,
  formatTimestamp,
  shortArtifactId,
} from '../../features/artifacts/artifactLibraryFilters'
import { useCompareArtifactsMutation } from '../../features/cases/useCompareArtifactsMutation'
import styles from './ArtifactsPanel.module.css'

type Props = {
  caseUuid: string
  artifacts: CaseSavedArtifactSummary[]
  leftUuid: string | null
  rightUuid: string | null
  onClear: () => void
}

function findArtifact(
  artifacts: CaseSavedArtifactSummary[],
  uuid: string | null,
): CaseSavedArtifactSummary | null {
  if (!uuid) return null
  return artifacts.find((item) => item.artifact_uuid === uuid) ?? null
}

function renderCompareResult(result: ArtifactCompareResponse) {
  return (
    <div className={styles.stack}>
      <p className={styles.statusText} role="status">
        {result.retrieval_note ||
          'Comparison retrieved both official versions from the case record.'}{' '}
        Comparison is read-only and creates no new artifact.
      </p>
      <dl className={styles.dl}>
        <dt>Type</dt>
        <dd>{artifactTypeLabel(String(result.artifact_type))}</dd>
        <dt>Version delta</dt>
        <dd>
          {result.version_delta == null ? '—' : String(result.version_delta)}
        </dd>
      </dl>
      <div className={styles.compareGrid}>
        <div className={styles.compareColumn}>
          <h4 className={styles.sectionHeading}>Left</h4>
          <p className={styles.itemTitle}>{result.left.title}</p>
          <p className={styles.metaRow}>
            v{result.left.version_number} ·{' '}
            {formatTimestamp(result.left.saved_at)} ·{' '}
            {shortArtifactId(result.left.artifact_uuid)}
          </p>
        </div>
        <div className={styles.compareColumn}>
          <h4 className={styles.sectionHeading}>Right</h4>
          <p className={styles.itemTitle}>{result.right.title}</p>
          <p className={styles.metaRow}>
            v{result.right.version_number} ·{' '}
            {formatTimestamp(result.right.saved_at)} ·{' '}
            {shortArtifactId(result.right.artifact_uuid)}
          </p>
        </div>
      </div>
      <section>
        <h4 className={styles.sectionHeading}>Changed summary keys</h4>
        {result.changed_summary_keys.length === 0 ? (
          <p className={styles.empty}>No changed summary keys.</p>
        ) : (
          <ul className={styles.keyList}>
            {result.changed_summary_keys.map((key) => (
              <li key={key}>{key}</li>
            ))}
          </ul>
        )}
      </section>
      <section>
        <h4 className={styles.sectionHeading}>Left-only summary keys</h4>
        {result.left_only_summary_keys.length === 0 ? (
          <p className={styles.empty}>None.</p>
        ) : (
          <ul className={styles.keyList}>
            {result.left_only_summary_keys.map((key) => (
              <li key={key}>{key}</li>
            ))}
          </ul>
        )}
      </section>
      <section>
        <h4 className={styles.sectionHeading}>Right-only summary keys</h4>
        {result.right_only_summary_keys.length === 0 ? (
          <p className={styles.empty}>None.</p>
        ) : (
          <ul className={styles.keyList}>
            {result.right_only_summary_keys.map((key) => (
              <li key={key}>{key}</li>
            ))}
          </ul>
        )}
      </section>
    </div>
  )
}

export function ArtifactComparePanel({
  caseUuid,
  artifacts,
  leftUuid,
  rightUuid,
  onClear,
}: Props) {
  const compareMutation = useCompareArtifactsMutation(caseUuid)
  const left = findArtifact(artifacts, leftUuid)
  const right = findArtifact(artifacts, rightUuid)
  const compatibility = canCompareArtifacts(left, right)

  return (
    <section className={styles.section} aria-labelledby="artifact-compare-heading">
      <h3 id="artifact-compare-heading" className={styles.sectionHeading}>
        Compare artifacts
      </h3>
      <p className={styles.subhead}>
        Select two compatible official artifacts of the same type. Comparison
        does not create a new official artifact.
      </p>
      <div className={styles.metaRow}>
        <span>
          Left:{' '}
          {left
            ? `${left.title || artifactTypeLabel(left.artifact_type)} (v${left.version_number})`
            : 'None'}
        </span>
        <span>
          Right:{' '}
          {right
            ? `${right.title || artifactTypeLabel(right.artifact_type)} (v${right.version_number})`
            : 'None'}
        </span>
      </div>
      {!compatibility.ok && (leftUuid || rightUuid) ? (
        <div className={styles.warningBox} role="status">
          {compatibility.reason}
        </div>
      ) : null}
      <div className={styles.exportRow}>
        <button
          type="button"
          className={styles.button}
          disabled={!compatibility.ok || compareMutation.isPending}
          aria-busy={compareMutation.isPending}
          onClick={() => {
            if (!leftUuid || !rightUuid || !compatibility.ok) return
            compareMutation.mutate({
              left_artifact_uuid: leftUuid,
              right_artifact_uuid: rightUuid,
            })
          }}
        >
          {compareMutation.isPending ? 'Comparing…' : 'Compare selected'}
        </button>
        <button
          type="button"
          className={styles.secondaryButton}
          onClick={() => {
            compareMutation.reset()
            onClear()
          }}
        >
          Clear selection
        </button>
      </div>
      {compareMutation.isError ? (
        <div className={styles.errorBox} role="alert">
          {compareMutation.error instanceof ApiError
            ? compareMutation.error.message
            : 'Unable to compare artifacts.'}
        </div>
      ) : null}
      {compareMutation.data ? renderCompareResult(compareMutation.data) : null}
    </section>
  )
}
