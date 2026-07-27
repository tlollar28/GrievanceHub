import { useQuery } from '@tanstack/react-query'
import { listGrievanceArtifacts } from '../../api/grievances'
import type { CaseSavedArtifactSummary } from '../../api/types/grievances'
import { isSupportedGrievanceTemplateId } from '../grievance/templateFields'
import { grievanceKeys } from './savedCaseActions'

/** Keep only official Step 1 / Step 2 grievance forms in the M6 list. */
export function filterSupportedGrievanceArtifacts(
  artifacts: CaseSavedArtifactSummary[],
): CaseSavedArtifactSummary[] {
  return artifacts.filter(
    (item) =>
      item.artifact_type === 'grievance_form' &&
      isSupportedGrievanceTemplateId(item.template_id),
  )
}

export function useGrievanceArtifactsQuery(
  caseUuid: string,
  enabled = true,
) {
  return useQuery({
    queryKey: grievanceKeys.list(caseUuid),
    enabled: enabled && caseUuid.length > 0,
    queryFn: ({ signal }) => listGrievanceArtifacts(caseUuid, signal),
    placeholderData: (previous) => previous,
    select: (data) => ({
      ...data,
      artifacts: filterSupportedGrievanceArtifacts(data.artifacts ?? []),
      groups: {
        ...data.groups,
        grievances: filterSupportedGrievanceArtifacts(
          data.groups?.grievances ?? data.artifacts ?? [],
        ),
      },
    }),
  })
}
