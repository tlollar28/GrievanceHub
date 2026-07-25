import { useMutation, useQueryClient } from '@tanstack/react-query'
import { saveAndPrintGrievance } from '../../api/grievances'
import type {
  SaveAndPrintGrievanceRequest,
  SaveAndPrintResponse,
} from '../../api/types/grievances'
import { grievanceKeys, workspaceKeys } from './savedCaseActions'

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
    },
  })
}
