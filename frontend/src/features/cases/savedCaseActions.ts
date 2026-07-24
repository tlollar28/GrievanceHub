import type {
  ListSavedCasesParams,
  SavedCaseSummary,
  SavedCaseWorkspaceStatus,
} from '../../api/types/savedCases'

export type CaseClickAction = 'open_case' | 'reopen_case'

/**
 * Terminal workspace statuses that require reopen before navigation.
 * Matches SavedCaseService.open_case and the /ui verification shell.
 * (Python SavedCaseApiClient only checks "closed"; backend also blocks
 * settled/archived with action_taken=closed_requires_reopen.)
 */
const TERMINAL_WORKSPACE_STATUSES: ReadonlySet<SavedCaseWorkspaceStatus> =
  new Set(['closed', 'settled', 'archived'])

export function isTerminalWorkspaceStatus(
  status: SavedCaseWorkspaceStatus,
): boolean {
  return TERMINAL_WORKSPACE_STATUSES.has(status)
}

export function resolveCaseClickAction(
  summary: SavedCaseSummary,
): CaseClickAction {
  if (isTerminalWorkspaceStatus(summary.workspace_status)) {
    return 'reopen_case'
  }
  return 'open_case'
}

export const savedCaseKeys = {
  all: ['savedCases'] as const,
  lists: () => [...savedCaseKeys.all, 'list'] as const,
  list: (params: ListSavedCasesParams) =>
    [...savedCaseKeys.lists(), params] as const,
  details: () => [...savedCaseKeys.all, 'detail'] as const,
  detail: (caseUuid: string) =>
    [...savedCaseKeys.details(), caseUuid] as const,
}

export const workspaceKeys = {
  all: ['workspace'] as const,
  detail: (caseUuid: string) => [...workspaceKeys.all, caseUuid] as const,
}
