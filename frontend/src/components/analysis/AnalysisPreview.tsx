import type { AnalysisPreviewPayload } from '../../api/types/reports'
import { AnalysisReportView } from './AnalysisReportView'
import { AnalysisSaveActions } from './AnalysisSaveActions'
import styles from './AnalysisPanel.module.css'

type Props = {
  preview: AnalysisPreviewPayload
  busy: boolean
  busyMode: 'save' | 'save_and_print' | null
  onSave: () => void
  onSaveAndPrint: () => void
  onCancel: () => void
}

const TEMP_BANNER =
  'Unsaved temporary preview — Cancel discards this analysis. Save creates an official version.'

export function AnalysisPreview({
  preview,
  busy,
  busyMode,
  onSave,
  onSaveAndPrint,
  onCancel,
}: Props) {
  const report = preview.report_data
  const suggested =
    typeof preview.suggested_version_number_if_saved === 'number'
      ? preview.suggested_version_number_if_saved
      : null

  return (
    <section className={styles.section} aria-label="Temporary analysis preview">
      <div className={styles.tempBanner} role="status">
        {TEMP_BANNER}
        {suggested != null
          ? ` Save would create version ${suggested}.`
          : ''}
      </div>
      <AnalysisSaveActions
        disabled={!report}
        busy={busy}
        busyMode={busyMode}
        onSave={onSave}
        onSaveAndPrint={onSaveAndPrint}
        onCancel={onCancel}
      />
      {report ? (
        <AnalysisReportView
          report={report}
          mode="temporary"
          suggestedVersionNumber={suggested}
          retrievalGaps={preview.retrieval_gaps ?? null}
        />
      ) : (
        <p className={styles.empty} role="alert">
          Temporary preview is missing report content.
        </p>
      )}
    </section>
  )
}
