import { useId, useState } from 'react'
import { Link } from 'react-router-dom'
import type { CaseWorkspace } from '../../api/types/workspace'
import { formatStepType } from '../../features/cases/savedCaseFilters'
import { CaseMemoryPanel } from './CaseMemoryPanel'
import { CaseOverviewPanel } from './CaseOverviewPanel'
import { KnownFactsEditor } from './KnownFactsEditor'
import styles from './CaseRail.module.css'

type Props = {
  workspace: CaseWorkspace
  factsReadOnly?: boolean
}

function assetLabel(asset: {
  original_filename?: string | null
  filename?: string | null
  asset_uuid?: string
}): string {
  return (
    asset.original_filename ||
    asset.filename ||
    asset.asset_uuid ||
    'Uploaded asset'
  )
}

export function CaseRail({ workspace, factsReadOnly = false }: Props) {
  const navId = useId()
  const [expanded, setExpanded] = useState(true)
  const summary = workspace.workspace_summary
  const timeline = Array.isArray(workspace.timeline) ? workspace.timeline : []
  const uploads = Array.isArray(workspace.uploaded_assets)
    ? workspace.uploaded_assets
    : Array.isArray(workspace.assets)
      ? workspace.assets
      : []
  const artifacts = Array.isArray(workspace.official_artifacts)
    ? workspace.official_artifacts
    : []
  const step =
    summary?.current_step_type ??
    workspace.step_progression?.current_step_type ??
    null
  const workspaceStatus =
    summary?.workspace_status ??
    workspace.step_progression?.workspace_status ??
    workspace.status

  return (
    <>
      <button
        type="button"
        className={styles.mobileToggle}
        aria-expanded={expanded}
        aria-controls={navId}
        onClick={() => setExpanded((value) => !value)}
      >
        {expanded ? 'Hide case rail' : 'Show case rail'}
      </button>
      <nav
        id={navId}
        className={`${styles.rail} ${expanded ? '' : styles.railCollapsed}`}
        aria-label="Case rail"
      >
        <section
          className={styles.section}
          aria-labelledby="case-identity-heading"
        >
          <h2 id="case-identity-heading" className={styles.heading}>
            Case identity
          </h2>
          <dl className={styles.metaList}>
            <div>
              <dt>Title</dt>
              <dd>{workspace.title || 'Untitled case'}</dd>
            </div>
            {workspace.user_name ? (
              <div>
                <dt>Steward</dt>
                <dd>{workspace.user_name}</dd>
              </div>
            ) : null}
            {workspace.local_number ? (
              <div>
                <dt>Local number</dt>
                <dd>{workspace.local_number}</dd>
              </div>
            ) : null}
            <div>
              <dt>Workspace status</dt>
              <dd>{workspaceStatus || '—'}</dd>
            </div>
            <div>
              <dt>Current step</dt>
              <dd>
                {formatStepType(
                  step as
                    | 'step_1_initial'
                    | 'step_2_appeal'
                    | 'step_3_appeal'
                    | null,
                )}
              </dd>
            </div>
            <div>
              <dt>Messages</dt>
              <dd>{summary?.message_count ?? workspace.message_count ?? 0}</dd>
            </div>
          </dl>
        </section>

        <CaseOverviewPanel
          overview={workspace.case_overview}
          initialQuestion={workspace.initial_question}
        />

        <KnownFactsEditor
          caseUuid={workspace.case_uuid}
          knownFacts={workspace.known_facts}
          readOnly={factsReadOnly}
        />

        <section
          className={styles.section}
          aria-labelledby="case-workflow-heading"
        >
          <h2 id="case-workflow-heading" className={styles.heading}>
            Workflow
          </h2>
          <dl className={styles.metaList}>
            <div>
              <dt>Step</dt>
              <dd>
                {formatStepType(
                  step as
                    | 'step_1_initial'
                    | 'step_2_appeal'
                    | 'step_3_appeal'
                    | null,
                )}
              </dd>
            </div>
            <div>
              <dt>Status</dt>
              <dd>{workspaceStatus || '—'}</dd>
            </div>
            {workspace.case_overview?.explicit_workflow_state ? (
              <div>
                <dt>Explicit state</dt>
                <dd>{workspace.case_overview.explicit_workflow_state}</dd>
              </div>
            ) : null}
          </dl>
        </section>

        <section
          className={styles.section}
          aria-labelledby="case-timeline-heading"
        >
          <h2 id="case-timeline-heading" className={styles.heading}>
            Recent timeline
          </h2>
          {timeline.length === 0 ? (
            <p className={styles.empty}>No recent timeline events.</p>
          ) : (
            <ul className={styles.timeline}>
              {timeline
                .slice()
                .reverse()
                .slice(0, 8)
                .map((event, index) => {
                  const title =
                    typeof event.title === 'string'
                      ? event.title
                      : typeof event.event_type === 'string'
                        ? event.event_type
                        : 'Timeline event'
                  const stamp =
                    (typeof event.event_timestamp === 'string' &&
                      event.event_timestamp) ||
                    (typeof event.created_at === 'string' && event.created_at) ||
                    null
                  return (
                    <li
                      key={`${title}-${stamp ?? index}`}
                      className={styles.timelineItem}
                    >
                      <p className={styles.timelineTitle}>{title}</p>
                      {stamp ? (
                        <p className={styles.timelineMeta}>
                          <time dateTime={stamp}>
                            {new Date(stamp).toLocaleString()}
                          </time>
                        </p>
                      ) : null}
                    </li>
                  )
                })}
            </ul>
          )}
        </section>

        <section
          className={styles.section}
          aria-labelledby="case-uploads-heading"
        >
          <h2 id="case-uploads-heading" className={styles.heading}>
            Uploads
          </h2>
          {uploads.length === 0 ? (
            <p className={styles.empty}>
              No uploads in this workspace summary
              {typeof summary?.asset_count === 'number'
                ? ` (asset count: ${summary.asset_count})`
                : ''}
              .
            </p>
          ) : (
            <ul className={styles.list}>
              {uploads.slice(0, 5).map((asset, index) => (
                <li key={asset.asset_uuid ?? index}>{assetLabel(asset)}</li>
              ))}
            </ul>
          )}
          <p className={styles.empty}>
            <Link to={`/cases/${workspace.case_uuid}/evidence`}>
              Open Evidence
            </Link>
          </p>
        </section>

        {artifacts.length > 0 ? (
          <section
            className={styles.section}
            aria-labelledby="case-artifacts-heading"
          >
            <h2 id="case-artifacts-heading" className={styles.heading}>
              Artifact summary
            </h2>
            <ul className={styles.list}>
              {artifacts.slice(0, 5).map((artifact, index) => (
                <li key={artifact.artifact_uuid ?? index}>
                  {artifact.title ||
                    artifact.artifact_type ||
                    'Saved artifact'}
                  {typeof artifact.version_number === 'number'
                    ? ` (v${artifact.version_number})`
                    : ''}
                </li>
              ))}
            </ul>
          </section>
        ) : null}

        <CaseMemoryPanel memory={workspace.case_memory} />
      </nav>
    </>
  )
}
