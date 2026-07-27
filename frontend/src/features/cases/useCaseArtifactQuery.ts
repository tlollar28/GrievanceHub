import { useQuery } from '@tanstack/react-query'
import { getCaseArtifact } from '../../api/artifacts'
import { artifactKeys } from './savedCaseActions'

export function useCaseArtifactQuery(
  caseUuid: string,
  artifactUuid: string | null,
  enabled = true,
) {
  return useQuery({
    queryKey: artifactKeys.detail(caseUuid, artifactUuid ?? ''),
    enabled: enabled && caseUuid.length > 0 && Boolean(artifactUuid),
    queryFn: ({ signal }) =>
      getCaseArtifact(caseUuid, artifactUuid as string, signal),
    placeholderData: (previous) => previous,
  })
}
