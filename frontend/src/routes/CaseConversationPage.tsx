import { useOutletContext } from 'react-router-dom'
import { ConversationPanel } from '../components/conversation/ConversationPanel'
import type { CaseWorkspaceOutletContext } from './CaseWorkspacePage'

/** Center + research region for /cases/:caseUuid/conversation. */
export function CaseConversationPage() {
  const { workspace } = useOutletContext<CaseWorkspaceOutletContext>()

  return (
    <ConversationPanel
      caseUuid={workspace.case_uuid}
      caseStatus={workspace.status}
    />
  )
}
