import { useId } from 'react'
import { ApiError } from '../../api/client'
import type { CaseWorkspace } from '../../api/types/workspace'
import { useCaseWorkflowQuery } from '../../features/cases/useCaseWorkflowQuery'
import {
  buildProgressionMilestones,
  caseStatusLabel,
  isStep3WorkflowState,
  isTerminalCaseStatus,
  stepTypeLabel,
  workflowStateLabel,
} from '../../features/workflow/workflowLabels'
import { LifecycleControls } from './LifecycleControls'
import { RecordOutcomeForm } from './RecordOutcomeForm'
import { WorkflowProgression } from './WorkflowProgression'
import styles from './WorkflowPanel.module.css'

type Props = {
  caseUuid: string
  workspace: CaseWorkspace
}

function asRecord(value: unknown): Record<string, unknown> | null {
  if (value && typeof value === 'object' && !Array.isArray(value)) {
    return value as Record<string, unknown>
  }
  return null
}

export function WorkflowPanel({ caseUuid, workspace }: Props) {
  const headingId = useId()
  const workflowQuery = useCaseWorkflowQuery(caseUuid)

  const workflow = workflowQuery.data
  const overview = asRecord(workspace.case_overview)
  const progression = asRecord(workspace.step_progression)
  const memory = asRecord(workspace.case_memory)

  const explicitState =
    workflow?.explicit_state ??
    (typeof overview?.explicit_workflow_state === 'string'
      ? overview.explicit_workflow_state
      : null) ??
    (typeof asRecord(memory?.workflow)?.explicit_state === 'string'
      ? String(asRecord(memory?.workflow)?.explicit_state)
      : null)

  const currentStep =
    workflow?.current_grievance_step ??
    (typeof overview?.current_step === 'string' ? overview.current_step : null) ??
    (typeof progression?.current_step_type === 'string'
      ? progression.current_step_type
      : null) ??
    (typeof workspace.workspace_summary?.current_step_type === 'string'
      ? workspace.workspace_summary.current_step_type
      : null)

  const caseStatus =
    workflow?.case_status ??
    (typeof overview?.current_status === 'string'
      ? overview.current_status
      : null) ??
    (typeof workspace.workspace_summary?.workspace_status === 'string'
      ? workspace.workspace_summary.workspace_status
      : null) ??
    (typeof workspace.workspace_summary?.status === 'string'
      ? workspace.workspace_summary.status
      : null)

  const steps = Array.isArray(progression?.steps) ? progression.steps : []
  const currentStage = steps.find((item) => {
    const row = asRecord(item)
    return row?.step_type === currentStep
  })
  const currentStageRecord = asRecord(currentStage)
  const stepStatus =
    typeof currentStageRecord?.status === 'string'
      ? currentStageRecord.status
      : null
  const stepClosed = currentStageRecord?.is_closed === true
  const templateId =
    typeof currentStageRecord?.template_id === 'string'
      ? currentStageRecord.template_id
      : null
  const templateAvailability =
    typeof currentStageRecord?.template_availability === 'string'
      ? currentStageRecord.template_availability
      : null

  const outcomes = Array.isArray(currentStageRecord?.outcomes)
    ? currentStageRecord.outcomes
    : []
  const latestOutcome = asRecord(outcomes[outcomes.length - 1])

  const milestones = buildProgressionMilestones({
    explicitState,
    currentStep,
    caseStatus,
  })

  const permitted = workflow?.permitted_next_states ?? []
  const terminal = isTerminalCaseStatus(caseStatus)
  const showStep3Boundary =
    isStep3WorkflowState(explicitState) ||
    Boolean(currentStep && currentStep.includes('step_3'))

  const loadError =
    workflowQuery.isError && !workflowQuery.data
      ? workflowQuery.error instanceof ApiError
        ? workflowQuery.error.message
        : 'Unable to load workflow state.'
      : null

  const caseTitle =
    workspace.workspace_summary?.title ||
    workspace.title ||
    `Case ${caseUuid}`

  return (
    <div className={styles.panel}>
      <header className={styles.header}>
        <h2 id={headingId} className={styles.heading}>
          Workflow &amp; outcomes
        </h2>
        <p className={styles.subhead}>
          View the current workflow state, record management outcomes, appeal on
          the same case UUID, and close, settle, or archive when permitted. The
          application manages workflow; the steward manages the grievance.
        </p>
        <p className={styles.disclosure} role="note">
          Recording an outcome does not create analysis reports or grievance
          artifacts. Official form generation remains Step 1 and Step 2 only.
        </p>
      </header>

      {workflowQuery.isLoading && !workflow ? (
        <p role="status" aria-busy="true">
          Loading workflow state…
        </p>
      ) : null}

      {loadError ? (
        <p className={styles.errorSummary} role="alert">
          {loadError}
        </p>
      ) : null}

      <section className={styles.section} aria-labelledby={`${headingId}-overview`}>
        <h3 id={`${headingId}-overview`} className={styles.sectionHeading}>
          Current workflow
        </h3>
        <dl className={styles.metaGrid}>
          <div className={styles.metaItem}>
            <dt>Case status</dt>
            <dd>{caseStatusLabel(caseStatus)}</dd>
          </div>
          <div className={styles.metaItem}>
            <dt>Workflow state</dt>
            <dd>
              {workflowStateLabel(explicitState)}
              {explicitState ? (
                <div className={styles.rawValue}>{explicitState}</div>
              ) : null}
            </dd>
          </div>
          <div className={styles.metaItem}>
            <dt>Current grievance step</dt>
            <dd>{stepTypeLabel(currentStep)}</dd>
          </div>
          <div className={styles.metaItem}>
            <dt>Step status</dt>
            <dd>
              {stepStatus
                ? stepStatus.replace(/_/g, ' ')
                : 'Not reported'}
              {stepClosed ? ' (closed)' : ' (open)'}
            </dd>
          </div>
          <div className={styles.metaItem}>
            <dt>Template availability</dt>
            <dd>
              {templateAvailability ?? 'Not reported'}
              {templateId ? (
                <div className={styles.rawValue}>{templateId}</div>
              ) : null}
            </dd>
          </div>
          <div className={styles.metaItem}>
            <dt>Latest outcome</dt>
            <dd>
              {latestOutcome
                ? `${String(latestOutcome.outcome_type ?? '—')}${
                    latestOutcome.decision_summary
                      ? `: ${String(latestOutcome.decision_summary)}`
                      : ''
                  }`
                : 'None recorded for current step'}
            </dd>
          </div>
          <div className={styles.metaItem}>
            <dt>Inference</dt>
            <dd>
              {workflow
                ? `${workflow.inference_confidence}${
                    workflow.inferred ? ' (inferred)' : ' (confirmed)'
                  }`
                : '—'}
            </dd>
          </div>
          <div className={styles.metaItem}>
            <dt>Terminal status</dt>
            <dd>{terminal ? 'Yes — reopen required for further work' : 'No'}</dd>
          </div>
        </dl>

        <div>
          <h4
            id={`${headingId}-permitted`}
            className={styles.sectionHeading}
          >
            Permitted next states
          </h4>
          {permitted.length > 0 ? (
            <ul
              className={styles.transitionList}
              aria-labelledby={`${headingId}-permitted`}
            >
              {permitted.map((state) => (
                <li key={state} className={styles.transitionChip}>
                  <span className={styles.visuallyHidden}>Raw state </span>
                  {workflowStateLabel(state)}
                  <span className={styles.rawValue}> ({state})</span>
                </li>
              ))}
            </ul>
          ) : (
            <p className={styles.fieldHint}>
              No permitted next FSM states returned for the current state.
            </p>
          )}
          <p className={styles.fieldHint}>
            Steward actions use Record Outcome and Lifecycle controls below.
            Generic FSM transition buttons are not exposed.
          </p>
        </div>
      </section>

      <section
        className={styles.section}
        aria-labelledby={`${headingId}-progression`}
      >
        <h3 id={`${headingId}-progression`} className={styles.sectionHeading}>
          Progression
        </h3>
        <WorkflowProgression milestones={milestones} />
        {showStep3Boundary ? (
          <p className={styles.warningDisclosure} role="note">
            Step 3 workflow tracking is available. Official Step 3 form
            generation is not supported. Official grievance generation ends at
            Step 2.
          </p>
        ) : null}
      </section>

      {!terminal ? (
        <RecordOutcomeForm
          caseUuid={caseUuid}
          caseTitle={caseTitle}
          currentStepType={currentStep}
        />
      ) : (
        <section className={styles.section}>
          <h3 className={styles.sectionHeading}>Record outcome</h3>
          <p className={styles.statusBanner} role="status">
            Outcome recording is unavailable while the case is terminal. Reopen
            the case to continue workflow actions.
          </p>
        </section>
      )}

      <LifecycleControls
        caseUuid={caseUuid}
        caseTitle={caseTitle}
        caseStatus={caseStatus}
      />
    </div>
  )
}
