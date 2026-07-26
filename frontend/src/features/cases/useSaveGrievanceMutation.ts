import { useMutation, useQueryClient } from '@tanstack/react-query'
import { saveAndPrintGrievance } from '../../api/grievances'
import type {
  SaveAndPrintGrievanceRequest,
  SaveAndPrintResponse,
} from '../../api/types/grievances'
import {
  artifactKeys,
  grievanceKeys,
  workflowKeys,
  workspaceKeys,
} from './savedCaseActions'

export type SaveGrievanceInput = {
  caseUuid: string
  body: SaveAndPrintGrievanceRequest
  signal?: AbortSignal
}

export function useSaveGrievanceMutation() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: async ({
      caseUuid,
      body,
      signal,
    }: SaveGrievanceInput): Promise<SaveAndPrintResponse> => {
      return saveAndPrintGrievance(caseUuid, body, signal)
    },
    retry: false,
    onSuccess: (_result, variables) => {
      void queryClient.invalidateQueries({
        queryKey: grievanceKeys.list(variables.caseUuid),
      })
      void queryClient.invalidateQueries({
        queryKey: [...grievanceKeys.details(), variables.caseUuid],
      })
      void queryClient.invalidateQueries({
        queryKey: workspaceKeys.detail(variables.caseUuid),
      })
      // Save and Save and Print also create/update a CaseSavedArtifact
      // (clearing the prior latest-official flag), append a timeline
      // event, and attempt a workflow transition — refresh the durable
      // resources those side effects actually change.
      void queryClient.invalidateQueries({
        queryKey: [...artifactKeys.lists(), variables.caseUuid],
      })
      void queryClient.invalidateQueries({
        queryKey: [...artifactKeys.details(), variables.caseUuid],
      })
      void queryClient.invalidateQueries({
        queryKey: [...artifactKeys.histories(), variables.caseUuid],
      })
      void queryClient.invalidateQueries({
        queryKey: [...artifactKeys.timelines(), variables.caseUuid],
      })
      void queryClient.invalidateQueries({
        queryKey: workflowKeys.detail(variables.caseUuid),
      })
    },
  })
}
