import { useQuery } from '@tanstack/react-query'
import { getCaseWorkspace } from '../../api/savedCases'
import { workspaceKeys } from './savedCaseActions'

export function useCaseWorkspaceQuery(caseUuid: string, enabled = true) {
  return useQuery({
    queryKey: workspaceKeys.detail(caseUuid),
    queryFn: ({ signal }) => getCaseWorkspace(caseUuid, signal),
    enabled: enabled && caseUuid.length > 0,
  })
}
