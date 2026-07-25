import type {
  HistoryContextParams,
  ListArtifactsParams,
  ListCaseHistoryParams,
  ListCaseTimelineParams,
} from '../../api/types/artifacts'
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

/** TanStack Query keys for GET /cases/{uuid}/workspace */
export const workspaceKeys = {
  all: ['caseWorkspace'] as const,
  detail: (caseUuid: string) => [...workspaceKeys.all, caseUuid] as const,
}

/** TanStack Query keys for GET /cases/{uuid}/messages */
export const messageKeys = {
  all: ['caseMessages'] as const,
  lists: () => [...messageKeys.all, 'list'] as const,
  list: (
    caseUuid: string,
    pagination: { limit: number; offset: number; order: string },
  ) => [...messageKeys.lists(), caseUuid, pagination] as const,
}

/** TanStack Query keys for GET /cases/{uuid}/assets */
export const assetKeys = {
  all: ['caseAssets'] as const,
  lists: () => [...assetKeys.all, 'list'] as const,
  list: (
    caseUuid: string,
    filters: { category?: string | null } = {},
  ) => [...assetKeys.lists(), caseUuid, filters] as const,
  details: () => [...assetKeys.all, 'detail'] as const,
  detail: (caseUuid: string, assetUuid: string) =>
    [...assetKeys.details(), caseUuid, assetUuid] as const,
}

/** TanStack Query keys for analysis versions */
export const analysisKeys = {
  all: ['analysisVersions'] as const,
  lists: () => [...analysisKeys.all, 'list'] as const,
  list: (caseUuid: string) => [...analysisKeys.lists(), caseUuid] as const,
  details: () => ['analysisVersion'] as const,
  detail: (caseUuid: string, versionNumber: number) =>
    [...analysisKeys.details(), caseUuid, versionNumber] as const,
}

/** TanStack Query keys for saved grievance artifacts */
export const grievanceKeys = {
  all: ['grievanceArtifacts'] as const,
  lists: () => [...grievanceKeys.all, 'list'] as const,
  list: (caseUuid: string) => [...grievanceKeys.lists(), caseUuid] as const,
  details: () => ['grievanceArtifact'] as const,
  detail: (caseUuid: string, artifactUuid: string) =>
    [...grievanceKeys.details(), caseUuid, artifactUuid] as const,
}

/**
 * TanStack Query keys for M7 Artifact Library, Official Case Record,
 * timeline, jump-to-context, and comparison.
 */
export const artifactKeys = {
  all: ['caseArtifacts'] as const,
  lists: () => [...artifactKeys.all, 'list'] as const,
  list: (caseUuid: string, filters: ListArtifactsParams = {}) =>
    [...artifactKeys.lists(), caseUuid, filters] as const,
  details: () => [...artifactKeys.all, 'detail'] as const,
  detail: (caseUuid: string, artifactUuid: string) =>
    [...artifactKeys.details(), caseUuid, artifactUuid] as const,
  histories: () => [...artifactKeys.all, 'history'] as const,
  history: (caseUuid: string, params: ListCaseHistoryParams = {}) =>
    [...artifactKeys.histories(), caseUuid, params] as const,
  timelines: () => [...artifactKeys.all, 'timeline'] as const,
  timeline: (caseUuid: string, params: ListCaseTimelineParams = {}) =>
    [...artifactKeys.timelines(), caseUuid, params] as const,
  contexts: () => [...artifactKeys.all, 'context'] as const,
  context: (
    caseUuid: string,
    eventId: string,
    params: HistoryContextParams = {},
  ) => [...artifactKeys.contexts(), caseUuid, eventId, params] as const,
  compares: () => [...artifactKeys.all, 'compare'] as const,
  compare: (
    caseUuid: string,
    selection: { left: string; right: string },
  ) => [...artifactKeys.compares(), caseUuid, selection] as const,
}

/** TanStack Query keys for GET /cases/{uuid}/workflow */
export const workflowKeys = {
  all: ['caseWorkflow'] as const,
  detail: (caseUuid: string) => [...workflowKeys.all, caseUuid] as const,
}
