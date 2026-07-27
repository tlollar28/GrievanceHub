import { useState } from 'react'
import { Link } from 'react-router-dom'
import type { CaseWorkspace } from '../../api/types/workspace'
import type { SavedCaseWorkspaceStatus } from '../../api/types/savedCases'
import {
  caseDisplayTitle,
  formatStepType,
} from '../../features/cases/savedCaseFilters'
import { isTerminalWorkspaceStatus } from '../../features/cases/savedCaseActions'
import { WorkspaceStatusBadge } from '../cases/WorkspaceStatusBadge'
import styles from './CaseContextHeader.module.css'

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

type Props = {
  workspace: CaseWorkspace
  casesListHref?: string
}

export function CaseContextHeader({
  workspace,
  casesListHref = '/cases',
}: Props) {
  const [copyMessage, setCopyMessage] = useState<string | null>(null)
  const summary = workspace.workspace_summary
  const overview = workspace.case_overview ?? workspace.overview
  const status =
    asWorkspaceStatus(summary?.workspace_status) ??
    asWorkspaceStatus(overview?.current_status) ??
    asWorkspaceStatus(workspace.status)
  const step =
    summary?.current_step_type ??
    overview?.current_step ??
    workspace.step_progression?.current_step_type ??
    null
  const stepStatus =
    typeof workspace.step_progression?.steps === 'object' &&
    Array.isArray(workspace.step_progression.steps) &&
    workspace.step_progression.steps[0] &&
    typeof workspace.step_progression.steps[0] === 'object' &&
    workspace.step_progression.steps[0] !== null &&
    'status' in workspace.step_progression.steps[0]
      ? String(
          (workspace.step_progression.steps[0] as { status?: unknown }).status ??
            '',
        )
      : null
  const title = caseDisplayTitle({
    title: workspace.title ?? summary?.title,
    issue_summary: overview?.issue ?? workspace.initial_question,
  })
  const caseNumber =
    overview?.case_number ?? workspace.local_number ?? null
  const lastActivity = overview?.last_activity_at ?? workspace.updated_at
  const isTerminal = status ? isTerminalWorkspaceStatus(status) : false

  async function handleCopyUuid() {
    try {
      await navigator.clipboard.writeText(workspace.case_uuid)
      setCopyMessage('Case UUID copied')
    } catch {
      setCopyMessage('Unable to copy UUID')
    }
  }

  return (
    <header className={styles.header} aria-labelledby="case-workspace-heading">
      <div className={styles.identity}>
        <div className={styles.titleRow}>
          <h1
            id="case-workspace-heading"
            className={styles.title}
            tabIndex={-1}
          >
            {title}
          </h1>
          {status ? <WorkspaceStatusBadge status={status} /> : null}
        </div>

        <dl className={styles.meta}>
          {caseNumber ? (
            <div className={styles.metaItem}>
              <dt>Case number</dt>
              <dd>{caseNumber}</dd>
            </div>
          ) : null}
          <div className={styles.metaItem}>
            <dt>Case UUID</dt>
            <dd>
              <div className={styles.uuidRow}>
                <code className={styles.uuid}>{workspace.case_uuid}</code>
                <button
                  type="button"
                  className={styles.copyButton}
                  onClick={() => {
                    void handleCopyUuid()
                  }}
                >
                  Copy UUID
                </button>
                {copyMessage ? (
                  <p className={styles.copyStatus} role="status">
                    {copyMessage}
                  </p>
                ) : null}
              </div>
            </dd>
          </div>
          <div className={styles.metaItem}>
            <dt>Current step</dt>
            <dd>
              {formatStepType(
                step as
                  | 'step_1_initial'
                  | 'step_2_appeal'
                  | 'step_3_appeal'
                  | null,
              )}
              {stepStatus ? ` · ${stepStatus}` : ''}
            </dd>
          </div>
          {lastActivity ? (
            <div className={styles.metaItem}>
              <dt>Last activity</dt>
              <dd>
                <time dateTime={lastActivity}>
                  {new Date(lastActivity).toLocaleString()}
                </time>
              </dd>
            </div>
          ) : null}
        </dl>

        {isTerminal ? (
          <p className={styles.terminalNote} role="status">
            This case is {status}. Lifecycle actions are not available in this
            milestone. Return to Saved Cases to reopen when needed.
          </p>
        ) : null}
      </div>

      <div className={styles.actions}>
        <Link className={styles.backLink} to={casesListHref}>
          Back to Cases
        </Link>
      </div>
    </header>
  )
}
