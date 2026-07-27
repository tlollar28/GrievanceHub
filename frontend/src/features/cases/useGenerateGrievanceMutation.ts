import { useMutation } from '@tanstack/react-query'
import {
  extractGrievanceGeneration,
  flattenFieldValues,
  generateGrievance,
  isSupportedGrievanceDraft,
} from '../../api/grievances'
import type {
  GenerateGrievanceResponse,
  TemporaryGrievanceDraft,
} from '../../api/types/grievances'
import { isSupportedGrievanceTemplateId } from '../grievance/templateFields'
import { ApiError } from '../../api/client'

export type GenerateGrievanceInput = {
  caseUuid: string
  signal?: AbortSignal
}

export type GenerateGrievanceResult = {
  response: GenerateGrievanceResponse
  draft: TemporaryGrievanceDraft | null
  unsupportedTemplateId: string | null
  prerequisitesNotMet: boolean
}

export function useGenerateGrievanceMutation() {
  return useMutation({
    mutationFn: async ({
      caseUuid,
      signal,
    }: GenerateGrievanceInput): Promise<GenerateGrievanceResult> => {
      const response = await generateGrievance(caseUuid, signal)

      if (response.status === 'prerequisites_not_met') {
        return {
          response,
          draft: null,
          unsupportedTemplateId: null,
          prerequisitesNotMet: true,
        }
      }

      if (response.status === 'case_not_found') {
        throw new ApiError({
          status: 404,
          message: response.message || 'Case not found.',
          path: `/cases/${caseUuid}/actions`,
          code: 'case_not_found',
        })
      }

      const generation = extractGrievanceGeneration(response)
      if (!generation) {
        throw new Error('Generate Grievance returned no draft payload.')
      }

      if (!isSupportedGrievanceDraft(generation)) {
        return {
          response,
          draft: null,
          unsupportedTemplateId: generation.template_id ?? 'unknown',
          prerequisitesNotMet: false,
        }
      }

      if (!isSupportedGrievanceTemplateId(generation.template_id)) {
        return {
          response,
          draft: null,
          unsupportedTemplateId: generation.template_id ?? 'unknown',
          prerequisitesNotMet: false,
        }
      }

      const fieldValues = flattenFieldValues(generation.field_values)
      const draft: TemporaryGrievanceDraft = {
        template_id: generation.template_id,
        step_type: generation.step_type ?? null,
        draft_status: generation.draft_status ?? null,
        field_values: fieldValues,
        steward_override_field_ids: [],
        generated_field_values: { ...fieldValues },
        message: generation.message ?? response.message ?? null,
      }

      return {
        response,
        draft,
        unsupportedTemplateId: null,
        prerequisitesNotMet: false,
      }
    },
    retry: false,
  })
}
