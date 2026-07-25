import { useQuery } from '@tanstack/react-query'
import { getCaseWorkflow } from '../../api/workflow'
import { workflowKeys } from './savedCaseActions'

export function useCaseWorkflowQuery(caseUuid: string, enabled = true) {
  return useQuery({
    queryKey: workflowKeys.detail(caseUuid),
    queryFn: ({ signal }) => getCaseWorkflow(caseUuid, signal),
    enabled: Boolean(caseUuid) && enabled,
  })
}
