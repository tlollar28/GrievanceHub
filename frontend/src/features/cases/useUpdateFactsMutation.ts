import { useMutation, useQueryClient } from '@tanstack/react-query'
import { updateCaseFacts } from '../../api/cases'
import type { KnownFacts, UpdateFactsResponse } from '../../api/types/cases'
import { workspaceKeys } from './savedCaseActions'

export type UpdateFactsInput = {
  caseUuid: string
  knownFacts: KnownFacts
}

export function useUpdateFactsMutation() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: ({
      caseUuid,
      knownFacts,
    }: UpdateFactsInput): Promise<UpdateFactsResponse> =>
      updateCaseFacts(caseUuid, { known_facts: knownFacts }),
    onSuccess: (_data, variables) => {
      void queryClient.invalidateQueries({
        queryKey: workspaceKeys.detail(variables.caseUuid),
      })
    },
  })
}
