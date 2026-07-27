import { useQuery } from '@tanstack/react-query'
import { fetchResearchMeta } from '../../api/research'
import { researchKeys } from './researchKeys'

export function useResearchMetaQuery() {
  return useQuery({
    queryKey: researchKeys.meta(),
    queryFn: ({ signal }) => fetchResearchMeta(signal),
    staleTime: 5 * 60_000,
  })
}
