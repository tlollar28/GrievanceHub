import { WorkspaceStatusBadge } from './WorkspaceStatusBadge'
import type { SavedCaseSummary } from '../../api/types/savedCases'
import {
  caseDisplayTitle,
  formatDateTime,
  formatStepType,
} from '../../features/cases/savedCaseFilters'
import { resolveCaseClickAction } from '../../features/cases/savedCaseActions'
import styles from './SavedCasesTable.module.css'

type Props = {
  cases: SavedCaseSummary[]
  activatingUuid: string | null
  onActivate: (summary: SavedCaseSummary, options?: { forceReopen?: boolean }) => void
  compact?: boolean
}

export function SavedCasesTable({
  cases,
  activatingUuid,
  onActivate,
  compact = false,
}: Props) {
  return (
    <div className={styles.wrap}>
      <table className={styles.table}>
        <caption className={styles.caption}>
          Saved cases{compact ? ' (recent)' : ''}
        </caption>
        <thead>
          <tr>
            <th scope="col">Case</th>
            <th scope="col">Step</th>
            <th scope="col">Status</th>
            {!compact ? <th scope="col">Last activity</th> : null}
            {!compact ? <th scope="col">Outcome</th> : null}
            <th scope="col">Actions</th>
          </tr>
        </thead>
        <tbody>
          {cases.map((summary) => {
            const busy = activatingUuid === summary.case_uuid
            const clickAction = resolveCaseClickAction(summary)
            const primaryLabel =
              clickAction === 'reopen_case' ? 'Reopen' : 'Open'
            const title = caseDisplayTitle(summary)

            return (
              <tr key={summary.case_uuid}>
                <td>
                  <button
                    type="button"
                    className={styles.caseButton}
                    onClick={() => onActivate(summary)}
                    disabled={busy}
                    aria-label={`${primaryLabel} ${title}`}
                  >
                    <span className={styles.caseTitle}>{title}</span>
                    <span className={styles.caseMeta}>
                      {summary.case_number
                        ? `No. ${summary.case_number}`
                        : summary.case_uuid.slice(0, 8)}
                      {summary.grievant_or_class
                        ? ` · ${summary.grievant_or_class}`
                        : ''}
                    </span>
                  </button>
                  {summary.issue_summary &&
                  summary.issue_summary !== summary.title ? (
                    <p className={styles.issue}>{summary.issue_summary}</p>
                  ) : null}
                </td>
                <td>
                  <div>{formatStepType(summary.current_step_type)}</div>
                  {summary.current_step_status ? (
                    <div className={styles.subtle}>
                      {summary.current_step_status.replaceAll('_', ' ')}
                    </div>
                  ) : null}
                </td>
                <td>
                  <WorkspaceStatusBadge status={summary.workspace_status} />
                </td>
                {!compact ? (
                  <td>{formatDateTime(summary.last_activity_at)}</td>
                ) : null}
                {!compact ? (
                  <td>
                    {summary.latest_outcome_summary ||
                      summary.latest_outcome_type ||
                      '—'}
                  </td>
                ) : null}
                <td>
                  <div className={styles.actions}>
                    {summary.available_actions.includes('open_case') &&
                    clickAction === 'open_case' ? (
                      <button
                        type="button"
                        className={styles.actionButton}
                        onClick={() => onActivate(summary)}
                        disabled={busy}
                      >
                        {busy ? 'Opening…' : 'Open'}
                      </button>
                    ) : null}
                    {summary.available_actions.includes('reopen_case') ||
                    clickAction === 'reopen_case' ? (
                      <button
                        type="button"
                        className={styles.actionButton}
                        onClick={() =>
                          onActivate(summary, { forceReopen: true })
                        }
                        disabled={busy}
                      >
                        {busy ? 'Reopening…' : 'Reopen'}
                      </button>
                    ) : null}
                  </div>
                </td>
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}
