import { useQuery } from '@tanstack/react-query'
import { getAnalysisVersion } from '../../api/reports'
import { analysisKeys } from './savedCaseActions'

export function useAnalysisVersionQuery(
  caseUuid: string,
  versionNumber: number | null,
  enabled = true,
) {
  return useQuery({
    queryKey:
      versionNumber != null
        ? analysisKeys.detail(caseUuid, versionNumber)
        : [...analysisKeys.details(), caseUuid, 'none'],
    queryFn: ({ signal }) => {
      if (versionNumber == null) {
        throw new Error('versionNumber is required')
      }
      return getAnalysisVersion(caseUuid, versionNumber, signal)
    },
    enabled: enabled && caseUuid.length > 0 && versionNumber != null,
    placeholderData: (previous) => previous,
  })
}
