import { useOutletContext } from 'react-router-dom'
import { SourcesResearchPanel } from '../components/research/SourcesResearchPanel'
import type { CaseWorkspaceOutletContext } from './CaseWorkspacePage'

/** Center region for /cases/:caseUuid/research (W6 M9). */
export function CaseResearchPage() {
  const { workspace } = useOutletContext<CaseWorkspaceOutletContext>()

  return <SourcesResearchPanel caseUuid={workspace.case_uuid} />
}
