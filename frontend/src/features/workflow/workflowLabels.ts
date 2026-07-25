import type { OutcomeType, WorkflowState } from '../../api/types/workflow'

const WORKFLOW_STATE_LABELS: Record<string, string> = {
  case_open: 'Case opened',
  step_1_analysis: 'Step 1 analysis in progress',
  step_1_draft: 'Step 1 grievance draft in progress',
  step_1_awaiting_steward_review: 'Step 1 awaiting steward review',
  step_1_official: 'Step 1 grievance is official',
  step_1_awaiting_management_response:
    'Awaiting or recording Step 1 management response',
  step_1_response_received: 'Step 1 management response received',
  step_1_decision_required: 'Step 1 decision required',
  step_1_resolved: 'Step 1 resolved',
  step_1_appealed: 'Step 1 appealed',
  step_2_analysis: 'Step 2 analysis in progress',
  step_2_draft: 'Step 2 grievance draft in progress',
  step_2_awaiting_steward_review: 'Step 2 awaiting steward review',
  step_2_official: 'Step 2 grievance is official',
  step_2_awaiting_management_response:
    'Awaiting or recording Step 2 management response',
  step_2_response_received: 'Step 2 management response received',
  step_2_decision_required: 'Step 2 decision required',
  step_2_resolved: 'Step 2 resolved',
  step_2_appealed: 'Step 2 appealed',
  step_3_analysis: 'Step 3 workflow — analysis tracking',
  step_3_draft: 'Step 3 workflow — draft tracking',
  step_3_awaiting_steward_review: 'Step 3 workflow — awaiting steward review',
  step_3_official: 'Step 3 workflow — official tracking',
  step_3_awaiting_management_response:
    'Step 3 workflow — awaiting management response',
  step_3_response_received: 'Step 3 workflow — response received',
  step_3_decision_required: 'Step 3 workflow — decision required',
  step_3_resolved: 'Step 3 resolved',
  settled: 'Case settled',
  closed: 'Case closed',
  reopened: 'Case reopened',
}

const STEP_TYPE_LABELS: Record<string, string> = {
  step_1_initial: 'Step 1 (initial grievance)',
  step_2_appeal: 'Step 2 (appeal)',
  step_3_appeal: 'Step 3 (workflow tracking)',
  step_1: 'Step 1',
  step_2: 'Step 2',
  step_3: 'Step 3',
}

const OUTCOME_TYPE_LABELS: Record<OutcomeType, string> = {
  pending: 'Pending',
  resolved: 'Resolved',
  granted: 'Granted',
  partially_granted: 'Partially granted',
  denied: 'Denied',
  withdrawn: 'Withdrawn',
  settled: 'Settled',
  appealed: 'Appealed',
  closed_no_appeal: 'Closed without appeal',
  unknown: 'Unknown',
}

const CASE_STATUS_LABELS: Record<string, string> = {
  open: 'Open',
  closed: 'Closed',
  settled: 'Settled',
  archived: 'Archived',
  reopened: 'Reopened',
  appealed: 'Appealed',
}

export function workflowStateLabel(state: WorkflowState | string | null | undefined): string {
  if (!state) return 'Unknown'
  return WORKFLOW_STATE_LABELS[state] ?? humanizeToken(state)
}

export function stepTypeLabel(step: string | null | undefined): string {
  if (!step) return 'No current step'
  return STEP_TYPE_LABELS[step] ?? humanizeToken(step)
}

export function outcomeTypeLabel(type: string | null | undefined): string {
  if (!type) return '—'
  if (type in OUTCOME_TYPE_LABELS) {
    return OUTCOME_TYPE_LABELS[type as OutcomeType]
  }
  return humanizeToken(type)
}

export function caseStatusLabel(status: string | null | undefined): string {
  if (!status) return 'Unknown'
  return CASE_STATUS_LABELS[status] ?? humanizeToken(status)
}

export function isStep3WorkflowState(state: string | null | undefined): boolean {
  return Boolean(state && state.startsWith('step_3'))
}

export function isTerminalWorkflowState(state: string | null | undefined): boolean {
  return state === 'closed' || state === 'settled'
}

export function isTerminalCaseStatus(status: string | null | undefined): boolean {
  return status === 'closed' || status === 'settled' || status === 'archived'
}

/** Progression milestones for the steward visualization (not a form checklist). */
export type ProgressionMilestoneId =
  | 'case_opened'
  | 'step_1'
  | 'step_2'
  | 'step_3'
  | 'terminal'

export type ProgressionMilestoneStatus =
  | 'completed'
  | 'current'
  | 'future'
  | 'unavailable'

export type ProgressionMilestone = {
  id: ProgressionMilestoneId
  label: string
  status: ProgressionMilestoneStatus
  detail: string
}

export function buildProgressionMilestones(options: {
  explicitState: string | null | undefined
  currentStep: string | null | undefined
  caseStatus: string | null | undefined
}): ProgressionMilestone[] {
  const state = options.explicitState ?? 'case_open'
  const step = options.currentStep ?? ''
  const caseStatus = options.caseStatus ?? ''

  const terminal =
    caseStatus === 'settled' ||
    state === 'settled' ||
    caseStatus === 'closed' ||
    state === 'closed' ||
    caseStatus === 'archived'

  const terminalLabel =
    caseStatus === 'settled' || state === 'settled'
      ? 'Settled'
      : caseStatus === 'archived'
        ? 'Archived'
        : 'Closed'

  const onStep3 =
    step.includes('step_3') || state.startsWith('step_3') || state === 'step_2_appealed'
  const onStep2 =
    !onStep3 &&
    (step.includes('step_2') ||
      state.startsWith('step_2') ||
      state === 'step_1_appealed')
  const onStep1 =
    !onStep2 &&
    !onStep3 &&
    !terminal &&
    (step.includes('step_1') ||
      state.startsWith('step_1') ||
      state === 'case_open' ||
      state === 'reopened')

  const step1Done = onStep2 || onStep3 || terminal
  const step2Done = onStep3 || (terminal && (onStep2 || step.includes('step_2') || state.startsWith('step_2')))
  const caseOpenedDone = true

  return [
    {
      id: 'case_opened',
      label: 'Case opened',
      status: caseOpenedDone
        ? onStep1 && state === 'case_open'
          ? 'current'
          : 'completed'
        : 'future',
      detail: 'Same case UUID for the full lifecycle.',
    },
    {
      id: 'step_1',
      label: 'Step 1',
      status: terminal && !step1Done
        ? 'completed'
        : onStep1
          ? 'current'
          : step1Done
            ? 'completed'
            : 'future',
      detail: 'Official Step 1 worksheet generation is supported.',
    },
    {
      id: 'step_2',
      label: 'Step 2',
      status: onStep2
        ? 'current'
        : step2Done || onStep3
          ? 'completed'
          : 'future',
      detail: 'Official Step 2 form generation is supported after appeal.',
    },
    {
      id: 'step_3',
      label: 'Step 3 (workflow only)',
      status: onStep3
        ? 'current'
        : 'unavailable',
      detail:
        'Workflow tracking may continue. Official Step 3 form generation is not supported.',
    },
    {
      id: 'terminal',
      label: terminal ? terminalLabel : 'Settled / Closed / Archived',
      status: terminal ? 'current' : 'future',
      detail: 'History and artifacts remain after terminal status.',
    },
  ]
}

export function describeOutcomeEffect(options: {
  outcomeType: string
  closeStep: boolean
  closeCase: boolean
  appealToNextStep: boolean
}): string {
  const parts: string[] = [
    `Records a ${outcomeTypeLabel(options.outcomeType).toLowerCase()} management decision for the current step.`,
  ]
  if (options.appealToNextStep) {
    parts.push(
      'Appeals to the next step on the same case UUID (does not create a new case).',
    )
  }
  if (options.closeStep && !options.appealToNextStep) {
    parts.push('Closes the current grievance step.')
  }
  if (options.closeCase) {
    parts.push(
      'Closes the case. Prior history and artifacts remain; reopen is available later.',
    )
  }
  if (
    !options.closeStep &&
    !options.closeCase &&
    !options.appealToNextStep
  ) {
    parts.push(
      'Does not close the step, close the case, or appeal unless you select those options.',
    )
  }
  parts.push('Does not create an analysis report or grievance artifact.')
  return parts.join(' ')
}

function humanizeToken(value: string): string {
  return value
    .replace(/_/g, ' ')
    .replace(/\b\w/g, (ch) => ch.toUpperCase())
}
