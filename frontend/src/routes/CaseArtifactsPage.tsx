import { useOutletContext } from 'react-router-dom'
import { ArtifactsPanel } from '../components/artifacts/ArtifactsPanel'
import type { CaseWorkspaceOutletContext } from './CaseWorkspacePage'

/** Center region for /cases/:caseUuid/artifacts (W6 M7). */
export function CaseArtifactsPage() {
  const { workspace } = useOutletContext<CaseWorkspaceOutletContext>()

  return <ArtifactsPanel caseUuid={workspace.case_uuid} />
}
