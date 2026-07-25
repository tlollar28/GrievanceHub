import { useMutation, useQueryClient } from '@tanstack/react-query'
import { uploadCaseAsset } from '../../api/assets'
import type {
  CaseAssetUploadResponse,
  UploadCaseAssetFields,
} from '../../api/types/assets'
import { assetKeys, workspaceKeys } from './savedCaseActions'

export type UploadAssetInput = {
  caseUuid: string
  fields: UploadCaseAssetFields
  signal?: AbortSignal
}

export function useUploadAssetMutation() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: async ({
      caseUuid,
      fields,
      signal,
    }: UploadAssetInput): Promise<CaseAssetUploadResponse> => {
      return uploadCaseAsset(caseUuid, fields, signal)
    },
    retry: false,
    onSuccess: (result, variables) => {
      void queryClient.invalidateQueries({
        queryKey: [...assetKeys.lists(), variables.caseUuid],
      })
      void queryClient.invalidateQueries({
        queryKey: workspaceKeys.detail(variables.caseUuid),
      })
      if (result.asset?.asset_uuid) {
        queryClient.setQueryData(
          assetKeys.detail(variables.caseUuid, result.asset.asset_uuid),
          result.asset,
        )
      }
    },
  })
}
