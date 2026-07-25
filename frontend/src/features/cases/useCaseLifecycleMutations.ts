import { useMutation, useQueryClient } from '@tanstack/react-query'
import { reopenSavedCase } from '../../api/savedCases'
import type { ReopenCaseRequest } from '../../api/types/savedCases'
import type {
  CaseArchiveRequest,
  CaseCloseRequest,
  CaseSettleRequest,
} from '../../api/types/workflow'
import {
  archiveSavedCase,
  closeSavedCase,
  settleSavedCase,
} from '../../api/workflow'
import {
  artifactKeys,
  savedCaseKeys,
  workflowKeys,
  workspaceKeys,
} from './savedCaseActions'

function invalidateLifecycleQueries(
  queryClient: ReturnType<typeof useQueryClient>,
  caseUuid: string,
) {
  void queryClient.invalidateQueries({
    queryKey: workflowKeys.detail(caseUuid),
  })
  void queryClient.invalidateQueries({
    queryKey: workspaceKeys.detail(caseUuid),
  })
  void queryClient.invalidateQueries({ queryKey: savedCaseKeys.all })
  void queryClient.invalidateQueries({
    queryKey: artifactKeys.timelines(),
  })
  void queryClient.invalidateQueries({
    queryKey: artifactKeys.histories(),
  })
}

export function useCloseCaseMutation(caseUuid: string) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (body: CaseCloseRequest) => closeSavedCase(caseUuid, body),
    retry: false,
    onSuccess: (data) => {
      if (data.workspace) {
        queryClient.setQueryData(workspaceKeys.detail(caseUuid), data.workspace)
      }
      invalidateLifecycleQueries(queryClient, caseUuid)
    },
  })
}

export function useSettleCaseMutation(caseUuid: string) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (body: CaseSettleRequest) => settleSavedCase(caseUuid, body),
    retry: false,
    onSuccess: (data) => {
      if (data.workspace) {
        queryClient.setQueryData(workspaceKeys.detail(caseUuid), data.workspace)
      }
      invalidateLifecycleQueries(queryClient, caseUuid)
    },
  })
}

export function useArchiveCaseMutation(caseUuid: string) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (body?: CaseArchiveRequest | null) =>
      archiveSavedCase(caseUuid, body ?? null),
    retry: false,
    onSuccess: (data) => {
      if (data.workspace) {
        queryClient.setQueryData(workspaceKeys.detail(caseUuid), data.workspace)
      }
      invalidateLifecycleQueries(queryClient, caseUuid)
    },
  })
}

export function useReopenCaseMutation(caseUuid: string) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (body: ReopenCaseRequest = { source: 'manual_ui' }) =>
      reopenSavedCase(caseUuid, body),
    retry: false,
    onSuccess: (data) => {
      if (data.workspace) {
        queryClient.setQueryData(workspaceKeys.detail(caseUuid), data.workspace)
      }
      invalidateLifecycleQueries(queryClient, caseUuid)
    },
  })
}
