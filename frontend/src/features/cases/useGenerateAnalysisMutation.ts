import { useMutation } from '@tanstack/react-query'
import {
  extractAnalysisPreview,
  generateAnalysisReport,
} from '../../api/reports'
import type {
  AnalysisPreviewPayload,
  GenerateAnalysisRequest,
  GenerateAnalysisResponse,
} from '../../api/types/reports'

export type GenerateAnalysisInput = {
  caseUuid: string
  body?: GenerateAnalysisRequest
  signal?: AbortSignal
}

export type GenerateAnalysisResult = {
  response: GenerateAnalysisResponse
  preview: AnalysisPreviewPayload
}

export function useGenerateAnalysisMutation() {
  return useMutation({
    mutationFn: async ({
      caseUuid,
      body,
      signal,
    }: GenerateAnalysisInput): Promise<GenerateAnalysisResult> => {
      const response = await generateAnalysisReport(caseUuid, body, signal)
      const preview = extractAnalysisPreview(response)
      if (!preview || typeof preview !== 'object') {
        throw new Error('Generate Analysis returned no temporary preview.')
      }
      return { response, preview }
    },
    retry: false,
  })
}
