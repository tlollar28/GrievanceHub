import { useQuery } from '@tanstack/react-query'
import { getHistoryContext } from '../../api/artifacts'
import type { HistoryContextParams } from '../../api/types/artifacts'
import { artifactKeys } from './savedCaseActions'

export function useHistoryContextQuery(
  caseUuid: string,
  eventId: string | null,
  params: HistoryContextParams = {},
  enabled = true,
) {
  return useQuery({
    queryKey: artifactKeys.context(caseUuid, eventId ?? '', params),
    enabled: enabled && caseUuid.length > 0 && Boolean(eventId),
    queryFn: ({ signal }) =>
      getHistoryContext(caseUuid, eventId as string, params, signal),
  })
}
