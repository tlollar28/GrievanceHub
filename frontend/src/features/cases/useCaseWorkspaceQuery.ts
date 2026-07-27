import { useQuery } from '@tanstack/react-query'
import { getCaseWorkspace } from '../../api/workspace'
import { workspaceKeys } from './savedCaseActions'

/**
 * Restores lean workspace for /cases/:caseUuid.
 * Uses cached open/reopen/create-seeded data immediately when present, then
 * refetches GET /cases/{uuid}/workspace as authoritative on mount.
 */
export function useCaseWorkspaceQuery(caseUuid: string, enabled = true) {
  return useQuery({
    queryKey: workspaceKeys.detail(caseUuid),
    queryFn: ({ signal }) => getCaseWorkspace(caseUuid, signal),
    enabled: enabled && caseUuid.length > 0,
    refetchOnMount: 'always',
  })
}
