import { useQuery } from '@tanstack/react-query'
import { listCaseArtifacts } from '../../api/artifacts'
import type { ListArtifactsParams } from '../../api/types/artifacts'
import { artifactKeys } from './savedCaseActions'

export function useCaseArtifactsQuery(
  caseUuid: string,
  filters: ListArtifactsParams = {},
  enabled = true,
) {
  return useQuery({
    queryKey: artifactKeys.list(caseUuid, filters),
    enabled: enabled && caseUuid.length > 0,
    queryFn: ({ signal }) => listCaseArtifacts(caseUuid, filters, signal),
    placeholderData: (previous) => previous,
  })
}
