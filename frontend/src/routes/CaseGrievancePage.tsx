import { useOutletContext } from 'react-router-dom'
import { GrievancePanel } from '../components/grievance/GrievancePanel'
import { isTerminalWorkspaceStatus } from '../features/cases/savedCaseActions'
import type { SavedCaseWorkspaceStatus } from '../api/types/savedCases'
import type { CaseWorkspaceOutletContext } from './CaseWorkspacePage'

/** Center region for /cases/:caseUuid/grievance. */
export function CaseGrievancePage() {
  const { workspace } = useOutletContext<CaseWorkspaceOutletContext>()
  const status = workspace.status as SavedCaseWorkspaceStatus | null | undefined
  const readOnly = status ? isTerminalWorkspaceStatus(status) : false

  return (
    <GrievancePanel
      caseUuid={workspace.case_uuid}
      savedBy={workspace.user_name}
      readOnly={readOnly}
      availableActions={workspace.available_actions}
    />
  )
}
