import { useQuery } from '@tanstack/react-query'
import { listAnalysisVersions } from '../../api/reports'
import { analysisKeys } from './savedCaseActions'

export function useAnalysisVersionsQuery(caseUuid: string, enabled = true) {
  return useQuery({
    queryKey: analysisKeys.list(caseUuid),
    queryFn: ({ signal }) => listAnalysisVersions(caseUuid, signal),
    enabled: enabled && caseUuid.length > 0,
    placeholderData: (previous) => previous,
  })
}
