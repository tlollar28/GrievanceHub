import type { CaseOverview } from '../../api/types/workspace'
import { formatStepType } from '../../features/cases/savedCaseFilters'
import styles from './CaseRail.module.css'

type Props = {
  overview: CaseOverview | null | undefined
  initialQuestion?: string | null
}

function hasContent(overview: CaseOverview | null | undefined): boolean {
  if (!overview) {
    return false
  }
  return Boolean(
    overview.issue ||
      overview.employee ||
      overview.current_recommendation ||
      (overview.open_questions && overview.open_questions.length > 0) ||
      (overview.outstanding_issues && overview.outstanding_issues.length > 0) ||
      overview.assigned_steward ||
      overview.explicit_workflow_state,
  )
}

export function CaseOverviewPanel({ overview, initialQuestion }: Props) {
  const issue = overview?.issue ?? initialQuestion ?? null
  const openQuestions = overview?.open_questions ?? []
  const outstanding = overview?.outstanding_issues ?? []

  if (!hasContent(overview) && !issue) {
    return (
      <section className={styles.section} aria-labelledby="case-overview-heading">
        <h2 id="case-overview-heading" className={styles.heading}>
          Case overview
        </h2>
        <p className={styles.empty}>
          No Case Overview content is available yet. Overview is maintained from
          Case Memory as the case progresses.
        </p>
      </section>
    )
  }

  return (
    <section className={styles.section} aria-labelledby="case-overview-heading">
      <h2 id="case-overview-heading" className={styles.heading}>
        Case overview
      </h2>

      <dl className={styles.metaList}>
        {overview?.employee ? (
          <div>
            <dt>Employee / grievant</dt>
            <dd>{overview.employee}</dd>
          </div>
        ) : null}
        {overview?.assigned_steward ? (
          <div>
            <dt>Assigned steward</dt>
            <dd>{overview.assigned_steward}</dd>
          </div>
        ) : null}
        {issue ? (
          <div>
            <dt>Issue</dt>
            <dd className={styles.bodyText}>{issue}</dd>
          </div>
        ) : null}
        {overview?.current_step ? (
          <div>
            <dt>Current step</dt>
            <dd>
              {formatStepType(
                overview.current_step as
                  | 'step_1_initial'
                  | 'step_2_appeal'
                  | 'step_3_appeal'
                  | null,
              )}
            </dd>
          </div>
        ) : null}
        {overview?.explicit_workflow_state ? (
          <div>
            <dt>Workflow state</dt>
            <dd>{overview.explicit_workflow_state}</dd>
          </div>
        ) : null}
        {overview?.current_status ? (
          <div>
            <dt>Status</dt>
            <dd>{overview.current_status}</dd>
          </div>
        ) : null}
      </dl>

      {overview?.current_recommendation ? (
        <div>
          <h3 className={styles.subheading}>Recommendation</h3>
          <p className={styles.bodyText}>{overview.current_recommendation}</p>
          <p className={styles.disclaimer}>
            Generated assessments are not source authority.
          </p>
        </div>
      ) : null}

      {openQuestions.length > 0 ? (
        <div>
          <h3 className={styles.subheading}>Open questions</h3>
          <ul className={styles.list}>
            {openQuestions.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
        </div>
      ) : (
        <p className={styles.empty}>No open questions recorded.</p>
      )}

      {outstanding.length > 0 ? (
        <div>
          <h3 className={styles.subheading}>Outstanding issues</h3>
          <ul className={styles.list}>
            {outstanding.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
        </div>
      ) : null}

      {overview ? (
        <dl className={styles.metaList}>
          <div>
            <dt>Evidence count</dt>
            <dd>{overview.evidence_count ?? 0}</dd>
          </div>
          <div>
            <dt>Analysis reports</dt>
            <dd>{overview.analysis_report_count ?? 0}</dd>
          </div>
          <div>
            <dt>Official grievances</dt>
            <dd>{overview.official_grievance_count ?? 0}</dd>
          </div>
        </dl>
      ) : null}
    </section>
  )
}
