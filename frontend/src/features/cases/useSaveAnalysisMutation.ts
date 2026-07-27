import { useMutation, useQueryClient } from '@tanstack/react-query'
import { saveAndPrintAnalysisReport } from '../../api/reports'
import type {
  SaveAndPrintReportRequest,
  SaveAndPrintResponse,
} from '../../api/types/reports'
import {
  analysisKeys,
  artifactKeys,
  workflowKeys,
  workspaceKeys,
} from './savedCaseActions'

export type SaveAnalysisInput = {
  caseUuid: string
  body: SaveAndPrintReportRequest
  signal?: AbortSignal
}

export function useSaveAnalysisMutation() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: async ({
      caseUuid,
      body,
      signal,
    }: SaveAnalysisInput): Promise<SaveAndPrintResponse> => {
      return saveAndPrintAnalysisReport(caseUuid, body, signal)
    },
    retry: false,
    onSuccess: (result, variables) => {
      void queryClient.invalidateQueries({
        queryKey: analysisKeys.list(variables.caseUuid),
      })
      void queryClient.invalidateQueries({
        queryKey: [...analysisKeys.details(), variables.caseUuid],
      })
      void queryClient.invalidateQueries({
        queryKey: workspaceKeys.detail(variables.caseUuid),
      })
      const version = result.artifact?.source_report_version_number
      if (typeof version === 'number') {
        void queryClient.invalidateQueries({
          queryKey: analysisKeys.detail(variables.caseUuid, version),
        })
      }
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
