import { useMutation } from '@tanstack/react-query'
import { compareCaseArtifacts } from '../../api/artifacts'
import type { CompareArtifactsRequest } from '../../api/types/artifacts'

export function useCompareArtifactsMutation(caseUuid: string) {
  return useMutation({
    mutationFn: (body: CompareArtifactsRequest) =>
      compareCaseArtifacts(caseUuid, body),
  })
}
