import { useQuery } from '@tanstack/react-query'
import { getGrievanceArtifact } from '../../api/grievances'
import { grievanceKeys } from './savedCaseActions'

export function useGrievanceArtifactQuery(
  caseUuid: string,
  artifactUuid: string | null,
  enabled = true,
) {
  return useQuery({
    queryKey: grievanceKeys.detail(caseUuid, artifactUuid ?? ''),
    enabled: enabled && caseUuid.length > 0 && Boolean(artifactUuid),
    queryFn: ({ signal }) =>
      getGrievanceArtifact(caseUuid, artifactUuid as string, signal),
    placeholderData: (previous) => previous,
  })
}
