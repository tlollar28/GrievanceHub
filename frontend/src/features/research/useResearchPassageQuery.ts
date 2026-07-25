import { useQuery } from '@tanstack/react-query'
import { fetchResearchPassage } from '../../api/research'
import { researchKeys } from './researchKeys'

export function useResearchPassageQuery(sourceChunkId: number | null) {
  return useQuery({
    queryKey:
      sourceChunkId != null
        ? researchKeys.passage(sourceChunkId)
        : [...researchKeys.all, 'passage', 'idle'],
    queryFn: ({ signal }) => {
      if (sourceChunkId == null) {
        throw new Error('Passage id is required')
      }
      return fetchResearchPassage(sourceChunkId, signal)
    },
    enabled: sourceChunkId != null,
    staleTime: 60_000,
  })
}
