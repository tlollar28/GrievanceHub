import { Link, useParams } from 'react-router-dom'
import { ApiError } from '../api/client'
import { WorkspaceStatusBadge } from '../components/cases/WorkspaceStatusBadge'
import { useCaseWorkspaceQuery } from '../features/cases/useCaseWorkspaceQuery'
import {
  caseDisplayTitle,
  formatStepType,
} from '../features/cases/savedCaseFilters'
import type { SavedCaseWorkspaceStatus } from '../api/types/savedCases'
import styles from './CaseWorkspaceEntryPage.module.css'

const WORKSPACE_STATUSES = new Set([
  'open',
  'closed',
  'reopened',
  'appealed',
  'settled',
  'archived',
])

function asWorkspaceStatus(
  value: string | null | undefined,
): SavedCaseWorkspaceStatus | null {
  if (!value || !WORKSPACE_STATUSES.has(value)) {
    return null
  }
  return value as SavedCaseWorkspaceStatus
}

/**
 * Minimal M1 workspace-entry route. Full CaseWorkspaceShell (chat, panels)
 * arrives in later milestones. This page confirms open/reopen succeeded and
 * surfaces lean identity from GET /cases/{uuid}/workspace (or Query cache).
 */
export function CaseWorkspaceEntryPage() {
  const { caseUuid = '' } = useParams()
  const query = useCaseWorkspaceQuery(caseUuid)

  if (!caseUuid) {
    return (
      <section className={styles.page} aria-labelledby="workspace-missing">
        <h1 id="workspace-missing">Case not specified</h1>
        <p>
          <Link to="/cases">Return to Cases</Link>
        </p>
      </section>
    )
  }

  if (query.isLoading) {
    return (
      <section className={styles.page} aria-labelledby="workspace-loading">
        <h1 id="workspace-loading">Opening case workspace…</h1>
        <p role="status">Loading case {caseUuid}</p>
      </section>
    )
  }

  if (query.isError) {
    const message =
      query.error instanceof ApiError
        ? query.error.message
        : 'Unable to load this case workspace.'
    return (
      <section className={styles.page} aria-labelledby="workspace-error">
        <h1 id="workspace-error">Case unavailable</h1>
        <p role="alert">{message}</p>
        <p>
          <Link to="/cases">Return to Cases</Link>
        </p>
      </section>
    )
  }

  const workspace = query.data
  const summary = workspace?.workspace_summary
  const status =
    asWorkspaceStatus(summary?.workspace_status) ??
    asWorkspaceStatus(workspace?.status) ??
    null
  const title = caseDisplayTitle({
    title: workspace?.title ?? summary?.title,
    issue_summary:
      typeof workspace?.overview === 'object' &&
      workspace.overview &&
      'issue' in workspace.overview
        ? (workspace.overview.issue as string | null)
        : null,
  })
  const step =
    (summary?.current_step_type as
      | 'step_1_initial'
      | 'step_2_appeal'
      | 'step_3_appeal'
      | null
      | undefined) ?? null

  return (
    <section className={styles.page} aria-labelledby="workspace-heading">
      <div className={styles.header}>
        <h1 id="workspace-heading">{title}</h1>
        {status ? <WorkspaceStatusBadge status={status} /> : null}
      </div>

      <dl className={styles.meta}>
        <div>
          <dt>Case UUID</dt>
          <dd>
            <code>{caseUuid}</code>
          </dd>
        </div>
        <div>
          <dt>Current step</dt>
          <dd>{formatStepType(step)}</dd>
        </div>
        <div>
          <dt>Messages</dt>
          <dd>{summary?.message_count ?? workspace?.message_count ?? '—'}</dd>
        </div>
        <div>
          <dt>Assets</dt>
          <dd>{summary?.asset_count ?? '—'}</dd>
        </div>
      </dl>

      <p className={styles.note}>
        Workspace entry succeeded. Conversation, evidence, analysis, and
        grievance panels arrive in later W6 milestones. Use Cases to return to
        the list or open another matter.
      </p>

      <p>
        <Link to="/cases">Back to Cases</Link>
      </p>
    </section>
  )
}
