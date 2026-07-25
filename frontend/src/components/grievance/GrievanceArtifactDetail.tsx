import { ApiError } from '../../api/client'
import { useGrievanceArtifactQuery } from '../../features/cases/useGrievanceArtifactQuery'
import {
  isSupportedGrievanceTemplateId,
  stepTypeLabel,
  templateDisplayName,
} from '../../features/grievance/templateFields'
import { GrievancePdfActions } from './GrievancePdfActions'
import styles from './GrievancePanel.module.css'

type Props = {
  caseUuid: string
  artifactUuid: string
}

export function GrievanceArtifactDetail({ caseUuid, artifactUuid }: Props) {
  const detailQuery = useGrievanceArtifactQuery(caseUuid, artifactUuid)
  const artifact = detailQuery.data

  if (detailQuery.isLoading && !artifact) {
    return (
      <p className={styles.skeleton} aria-busy="true">
        Loading saved grievance…
      </p>
    )
  }

  if (detailQuery.isError && !artifact) {
    const message =
      detailQuery.error instanceof ApiError
        ? detailQuery.error.message
        : 'Unable to load saved grievance.'
    return (
      <div className={styles.errorBox} role="alert">
        <p>{message}</p>
        <button
          type="button"
          className={styles.retryButton}
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
    return <p className={styles.empty}>Select a saved grievance artifact.</p>
  }

  if (!isSupportedGrievanceTemplateId(artifact.template_id)) {
    return (
      <div className={styles.warningBox} role="status">
        This saved entry is not an official Step 1 or Step 2 grievance form and
        is not shown in the M6 grievance workspace.
      </div>
    )
  }

  return (
    <div className={styles.report}>
      <header className={styles.reportHeader}>
        <h3 className={styles.reportTitle}>
          {artifact.title || templateDisplayName(artifact.template_id)}
        </h3>
        <div className={styles.metaRow}>
          <span className={styles.officialBadge}>Official</span>
          <span className={styles.versionMeta}>
            {templateDisplayName(artifact.template_id)}
          </span>
          <span className={styles.versionMeta}>
            {stepTypeLabel(artifact.grievance_step)}
          </span>
          <span className={styles.versionMeta}>
            Version {artifact.version_number}
          </span>
          <span className={styles.versionMeta}>
            PDF: {artifact.pdf_status ?? 'pending'}
          </span>
        </div>
      </header>

      <GrievancePdfActions
        caseUuid={caseUuid}
        artifactUuid={artifact.artifact_uuid}
        templateId={artifact.template_id}
        pdfStatus={artifact.pdf_status}
      />
    </div>
  )
}
