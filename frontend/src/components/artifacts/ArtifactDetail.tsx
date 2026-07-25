import { ApiError } from '../../api/client'
import type { CaseSavedArtifactDetail } from '../../api/types/artifacts'
import {
  artifactTypeLabel,
  formatTimestamp,
  pdfStatusLabel,
  shortArtifactId,
} from '../../features/artifacts/artifactLibraryFilters'
import { useCaseArtifactQuery } from '../../features/cases/useCaseArtifactQuery'
import {
  stepTypeLabel,
  templateDisplayName,
} from '../../features/grievance/templateFields'
import { ArtifactPdfActions } from './ArtifactPdfActions'
import styles from './ArtifactsPanel.module.css'

type Props = {
  caseUuid: string
  artifactUuid: string | null
}

function isPlainObject(value: unknown): value is Record<string, unknown> {
  return Boolean(value) && typeof value === 'object' && !Array.isArray(value)
}

function displayValue(value: unknown): string {
  if (value == null) return '—'
  if (typeof value === 'string') return value.trim() || '—'
  if (typeof value === 'number' || typeof value === 'boolean') {
    return String(value)
  }
  if (Array.isArray(value)) {
    return value.map((item) => displayValue(item)).join(', ') || '—'
  }
  return '—'
}

function extractFieldValues(
  artifact: CaseSavedArtifactDetail,
): Record<string, string> | null {
  const content = artifact.content_json
  if (!isPlainObject(content)) return null
  const fieldValues = content.field_values
  if (!isPlainObject(fieldValues)) return null
  const out: Record<string, string> = {}
  for (const [key, value] of Object.entries(fieldValues)) {
    out[key] = displayValue(value)
  }
  return out
}

function extractAnalysisSummary(
  artifact: CaseSavedArtifactDetail,
): Array<{ label: string; value: string }> {
  const rows: Array<{ label: string; value: string }> = []
  const keySummary = artifact.key_summary
  if (isPlainObject(keySummary)) {
    for (const [key, value] of Object.entries(keySummary)) {
      if (key === 'key_field_values' || typeof value === 'object') continue
      rows.push({ label: key, value: displayValue(value) })
    }
  }
  const content = artifact.content_json
  if (isPlainObject(content)) {
    const reportData = isPlainObject(content.report_data)
      ? content.report_data
      : content
    const report = isPlainObject(reportData.report)
      ? reportData.report
      : reportData
    const quick = isPlainObject(report.quick_assessment)
      ? report.quick_assessment
      : null
    if (quick) {
      if (quick.summary != null) {
        rows.push({ label: 'Quick assessment', value: displayValue(quick.summary) })
      }
      if (quick.grievability != null) {
        rows.push({ label: 'Grievability', value: displayValue(quick.grievability) })
      }
      if (quick.confidence != null) {
        rows.push({ label: 'Confidence', value: displayValue(quick.confidence) })
      }
    }
  }
  return rows
}

function validationStatus(artifact: CaseSavedArtifactDetail): string | null {
  const content = artifact.content_json
  if (!isPlainObject(content)) return null
  const status = content.validation_status
  return typeof status === 'string' && status.trim() ? status : null
}

export function ArtifactDetail({ caseUuid, artifactUuid }: Props) {
  const detailQuery = useCaseArtifactQuery(caseUuid, artifactUuid)
  const artifact = detailQuery.data

  if (!artifactUuid) {
    return (
      <p className={styles.empty} role="status">
        Select an official artifact to view read-only details.
      </p>
    )
  }

  if (detailQuery.isLoading && !artifact) {
    return (
      <p className={styles.skeleton} aria-busy="true" role="status">
        Loading artifact details…
      </p>
    )
  }

  if (detailQuery.isError && !artifact) {
    const message =
      detailQuery.error instanceof ApiError
        ? detailQuery.error.message
        : 'Unable to load artifact details.'
    return (
      <div className={styles.errorBox} role="alert">
        <p>{message}</p>
        <button
          type="button"
          className={styles.secondaryButton}
          onClick={() => {
            void detailQuery.refetch()
          }}
        >
          Retry
        </button>
      </div>
    )
  }

  if (!artifact) {
    return (
      <p className={styles.empty} role="status">
        Artifact not found for this case.
      </p>
    )
  }

  const fieldValues =
    artifact.artifact_type === 'grievance_form'
      ? extractFieldValues(artifact)
      : null
  const analysisRows =
    artifact.artifact_type === 'analysis_report'
      ? extractAnalysisSummary(artifact)
      : []
  const validation = validationStatus(artifact)
  const typeLabel = artifactTypeLabel(artifact.artifact_type)

  return (
    <div className={styles.stack}>
      <header className={styles.detailHeader}>
        <h3 className={styles.detailTitle}>
          {artifact.title || typeLabel}
        </h3>
        <div className={styles.metaRow}>
          <span
            className={`${styles.badge} ${
              artifact.artifact_type === 'analysis_report'
                ? styles.badgeAnalysis
                : styles.badgeGrievance
            }`}
          >
            {typeLabel}
          </span>
          <span className={`${styles.badge} ${styles.badgeOfficial}`}>
            Official
          </span>
          <span className={styles.srOnly}>
            Artifact type: {typeLabel}. Status: official saved record.
            {pdfStatusLabel(artifact.pdf_status)}.
          </span>
        </div>
        <p className={styles.statusText} role="status">
          Read-only saved artifact. Opening this view does not regenerate or
          edit the record.
        </p>
      </header>

      <dl className={styles.dl}>
        <dt>Artifact ID</dt>
        <dd title={artifact.artifact_uuid}>
          {shortArtifactId(artifact.artifact_uuid)}
        </dd>
        <dt>Version</dt>
        <dd>
          {artifact.version_label || `v${artifact.version_number}`} (
          {artifact.version_number})
        </dd>
        <dt>Saved</dt>
        <dd>{formatTimestamp(artifact.saved_at)}</dd>
        {artifact.saved_by ? (
          <>
            <dt>Saved by</dt>
            <dd>{artifact.saved_by}</dd>
          </>
        ) : null}
        <dt>PDF</dt>
        <dd
          className={
            artifact.pdf_status === 'ready'
              ? styles.statusReady
              : artifact.pdf_status === 'failed'
                ? styles.statusFailed
                : styles.statusPending
          }
        >
          {pdfStatusLabel(artifact.pdf_status)}
          {artifact.printed ? ' · Print ready' : ''}
        </dd>
        {artifact.template_id ? (
          <>
            <dt>Template</dt>
            <dd>{templateDisplayName(artifact.template_id)}</dd>
          </>
        ) : null}
        {artifact.grievance_step ? (
          <>
            <dt>Step</dt>
            <dd>{stepTypeLabel(artifact.grievance_step)}</dd>
          </>
        ) : null}
        {artifact.source_report_version_number != null ? (
          <>
            <dt>Report version</dt>
            <dd>{artifact.source_report_version_number}</dd>
          </>
        ) : null}
        {validation ? (
          <>
            <dt>Validation</dt>
            <dd>{validation}</dd>
          </>
        ) : null}
        <dt>Latest official</dt>
        <dd>{artifact.is_latest_official ? 'Yes' : 'No'}</dd>
      </dl>

      {analysisRows.length > 0 ? (
        <section aria-labelledby="artifact-analysis-summary">
          <h4 id="artifact-analysis-summary" className={styles.sectionHeading}>
            Saved report summary
          </h4>
          <dl className={styles.dl}>
            {analysisRows.map((row) => (
              <div key={row.label} style={{ display: 'contents' }}>
                <dt>{row.label}</dt>
                <dd>{row.value}</dd>
              </div>
            ))}
          </dl>
        </section>
      ) : null}

      {fieldValues ? (
        <section aria-labelledby="artifact-field-values">
          <h4 id="artifact-field-values" className={styles.sectionHeading}>
            Saved field values
          </h4>
          <dl className={styles.fields}>
            {Object.entries(fieldValues).map(([fieldId, value]) => (
              <div key={fieldId} className={styles.fieldRow}>
                <dt>{fieldId}</dt>
                <dd>{value}</dd>
              </div>
            ))}
          </dl>
        </section>
      ) : null}

      <ArtifactPdfActions
        caseUuid={caseUuid}
        artifactUuid={artifact.artifact_uuid}
        artifactType={artifact.artifact_type}
        title={artifact.title}
        pdfStatus={artifact.pdf_status}
      />
    </div>
  )
}
