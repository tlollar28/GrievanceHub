import { useQuery } from '@tanstack/react-query'
import { listCaseTimeline } from '../../api/artifacts'
import type { ListCaseTimelineParams } from '../../api/types/artifacts'
import { artifactKeys } from './savedCaseActions'

export function useCaseTimelineQuery(
  caseUuid: string,
  params: ListCaseTimelineParams = {},
  enabled = true,
) {
  return useQuery({
    queryKey: artifactKeys.timeline(caseUuid, params),
    enabled: enabled && caseUuid.length > 0,
    queryFn: ({ signal }) => listCaseTimeline(caseUuid, params, signal),
    placeholderData: (previous) => previous,
  })
}
