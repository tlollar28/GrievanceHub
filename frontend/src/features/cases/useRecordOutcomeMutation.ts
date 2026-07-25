import { useMutation, useQueryClient } from '@tanstack/react-query'
import { recordCaseOutcome } from '../../api/workflow'
import type { RecordStepOutcomeRequest } from '../../api/types/workflow'
import {
  artifactKeys,
  savedCaseKeys,
  workflowKeys,
  workspaceKeys,
} from './savedCaseActions'

export function useRecordOutcomeMutation(caseUuid: string) {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (body: RecordStepOutcomeRequest) =>
      recordCaseOutcome(caseUuid, body),
    retry: false,
    onSuccess: (data) => {
      if (data.workflow) {
        queryClient.setQueryData(workflowKeys.detail(caseUuid), data.workflow)
      }
      if (data.workspace) {
        queryClient.setQueryData(workspaceKeys.detail(caseUuid), data.workspace)
      }
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
      void queryClient.invalidateQueries({
        queryKey: artifactKeys.lists(),
      })
    },
  })
}
