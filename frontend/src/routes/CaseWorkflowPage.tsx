import { useOutletContext } from 'react-router-dom'
import { WorkflowPanel } from '../components/workflow/WorkflowPanel'
import type { CaseWorkspaceOutletContext } from './CaseWorkspacePage'

/** Center region for /cases/:caseUuid/workflow (W6 M8). */
export function CaseWorkflowPage() {
  const { workspace } = useOutletContext<CaseWorkspaceOutletContext>()

  return (
    <WorkflowPanel caseUuid={workspace.case_uuid} workspace={workspace} />
  )
}
