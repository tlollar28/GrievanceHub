import { useQuery } from '@tanstack/react-query'
import { listCaseHistory } from '../../api/artifacts'
import type { ListCaseHistoryParams } from '../../api/types/artifacts'
import { artifactKeys } from './savedCaseActions'

export function useCaseHistoryQuery(
  caseUuid: string,
  params: ListCaseHistoryParams = {},
  enabled = true,
) {
  return useQuery({
    queryKey: artifactKeys.history(caseUuid, params),
    enabled: enabled && caseUuid.length > 0,
    queryFn: ({ signal }) => listCaseHistory(caseUuid, params, signal),
    placeholderData: (previous) => previous,
  })
}
