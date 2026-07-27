import { useQuery } from '@tanstack/react-query'
import { getCaseAsset } from '../../api/assets'
import { assetKeys } from './savedCaseActions'

export function useCaseAssetQuery(
  caseUuid: string,
  assetUuid: string | null,
  enabled = true,
) {
  return useQuery({
    queryKey: assetKeys.detail(caseUuid, assetUuid ?? ''),
    queryFn: ({ signal }) => getCaseAsset(caseUuid, assetUuid!, signal),
    enabled: enabled && caseUuid.length > 0 && Boolean(assetUuid),
  })
}
