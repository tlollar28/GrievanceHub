import { useQuery } from '@tanstack/react-query'
import { searchResearchSources } from '../../api/research'
import type { ResearchSearchRequest } from '../../api/types/research'
import { researchKeys } from './researchKeys'

export function useResearchSearchQuery(
  request: ResearchSearchRequest | null,
  enabled: boolean,
) {
  return useQuery({
    queryKey: request
      ? researchKeys.search(request)
      : [...researchKeys.all, 'search', 'idle'],
    queryFn: ({ signal }) => {
      if (!request) {
        throw new Error('Research search request is required')
      }
      return searchResearchSources(request, signal)
    },
    enabled: enabled && request != null && request.query.trim().length > 0,
    staleTime: 60_000,
    // Deliberate search submission: steward can retry; avoid hidden multi-retry.
    retry: false,
  })
}
