import { useOutletContext } from 'react-router-dom'
import { EvidencePanel } from '../components/evidence/EvidencePanel'
import { isTerminalWorkspaceStatus } from '../features/cases/savedCaseActions'
import type { SavedCaseWorkspaceStatus } from '../api/types/savedCases'
import type { CaseWorkspaceOutletContext } from './CaseWorkspacePage'

/** Center region for /cases/:caseUuid/evidence. */
export function CaseEvidencePage() {
  const { workspace } = useOutletContext<CaseWorkspaceOutletContext>()
  const status = workspace.status as SavedCaseWorkspaceStatus | null | undefined
  const readOnly = status ? isTerminalWorkspaceStatus(status) : false

  return (
    <EvidencePanel
      caseUuid={workspace.case_uuid}
      uploadedBy={workspace.user_name}
      readOnly={readOnly}
    />
  )
}
