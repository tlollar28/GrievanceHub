import { useMutation, useQueryClient } from '@tanstack/react-query'
import { openSavedCase, reopenSavedCase } from '../../api/savedCases'
import type {
  OpenCaseResponse,
  ReopenCaseResponse,
  SavedCaseSummary,
} from '../../api/types/savedCases'
import {
  resolveCaseClickAction,
  savedCaseKeys,
  workspaceKeys,
} from './savedCaseActions'

export type ActivateCaseResult = OpenCaseResponse | ReopenCaseResponse

export type ActivateCaseInput = {
  summary: SavedCaseSummary
  forceReopen?: boolean
  reason?: string
}

export function useActivateCaseMutation() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: async ({
      summary,
      forceReopen = false,
      reason,
    }: ActivateCaseInput): Promise<ActivateCaseResult> => {
      const action = forceReopen
        ? 'reopen_case'
        : resolveCaseClickAction(summary)

      if (action === 'reopen_case') {
        return reopenSavedCase(summary.case_uuid, {
          source: 'manual_ui',
          reason: reason ?? null,
        })
      }

      return openSavedCase(summary.case_uuid, { source: 'manual_ui' })
    },
    onSuccess: (result) => {
      if (result.action_taken === 'closed_requires_reopen') {
        return
      }

      void queryClient.invalidateQueries({ queryKey: savedCaseKeys.lists() })

      if (result.workspace) {
        queryClient.setQueryData(
          workspaceKeys.detail(result.case.case_uuid),
          result.workspace,
        )
      }

      queryClient.setQueryData(
        savedCaseKeys.detail(result.case.case_uuid),
        result.case,
      )
    },
  })
}
