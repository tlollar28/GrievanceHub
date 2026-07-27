import { useQuery } from '@tanstack/react-query'
import { listCaseAssets } from '../../api/assets'
import type { ListCaseAssetsParams } from '../../api/types/assets'
import { assetKeys } from './savedCaseActions'

export function useCaseAssetsQuery(
  caseUuid: string,
  params: ListCaseAssetsParams = {},
  enabled = true,
) {
  const filters = {
    category: params.category ?? null,
  }

  return useQuery({
    queryKey: assetKeys.list(caseUuid, filters),
    queryFn: ({ signal }) => listCaseAssets(caseUuid, params, signal),
    enabled: enabled && caseUuid.length > 0,
    placeholderData: (previous) => previous,
  })
}
