import { useQuery } from '@tanstack/react-query'
import { listSavedCases } from '../../api/savedCases'
import type { ListSavedCasesParams } from '../../api/types/savedCases'
import { savedCaseKeys } from './savedCaseActions'

export function useSavedCasesQuery(params: ListSavedCasesParams) {
  return useQuery({
    queryKey: savedCaseKeys.list(params),
    queryFn: ({ signal }) => listSavedCases(params, signal),
  })
}
