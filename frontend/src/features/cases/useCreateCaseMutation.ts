import { useMutation, useQueryClient } from '@tanstack/react-query'
import { createCase } from '../../api/cases'
import type { CreateCaseRequest, CreateCaseResponse } from '../../api/types/cases'
import { savedCaseKeys } from './savedCaseActions'

export function useCreateCaseMutation() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (body: CreateCaseRequest): Promise<CreateCaseResponse> =>
      createCase(body),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: savedCaseKeys.lists() })
    },
  })
}
