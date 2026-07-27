import { ApiError } from '../../api/client'
import { useAnalysisVersionQuery } from '../../features/cases/useAnalysisVersionQuery'
import { AnalysisExportActions } from './AnalysisExportActions'
import { AnalysisReportView } from './AnalysisReportView'
import styles from './AnalysisPanel.module.css'

type Props = {
  caseUuid: string
  versionNumber: number
  artifactUuid?: string | null
}

export function AnalysisVersionDetail({
  caseUuid,
  versionNumber,
  artifactUuid,
}: Props) {
  const detailQuery = useAnalysisVersionQuery(caseUuid, versionNumber)
  const errorMessage =
    detailQuery.isError && !detailQuery.data
      ? detailQuery.error instanceof ApiError
        ? detailQuery.error.message
        : 'Unable to load saved analysis version.'
      : null

  if (detailQuery.isLoading && !detailQuery.data) {
    return (
      <p className={styles.skeleton} aria-busy="true">
        Loading saved version {versionNumber}…
      </p>
    )
  }

  if (errorMessage) {
    return (
      <div className={styles.errorBox} role="alert">
        <p>{errorMessage}</p>
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

  const detail = detailQuery.data
  const report = detail?.report_data
  if (!detail || !report) {
    return (
      <p className={styles.empty}>
        Saved version {versionNumber} has no report content.
      </p>
    )
  }

  return (
    <div className={styles.section}>
      <AnalysisReportView
        report={report}
        mode="saved"
        versionNumber={detail.version_number}
        retrievalGaps={detail.retrieval_gaps ?? null}
      />
      <AnalysisExportActions
        caseUuid={caseUuid}
        versionNumber={detail.version_number}
        artifactUuid={artifactUuid}
      />
    </div>
  )
}
