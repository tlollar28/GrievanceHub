import type { ResearchSearchRequest } from '../../api/types/research'

/** TanStack Query keys for read-only Sources Research (authority corpus). */
export const researchKeys = {
  all: ['sourceResearch'] as const,
  meta: () => [...researchKeys.all, 'meta'] as const,
  sources: (params: {
    limit: number
    offset: number
    sourceType?: string
  }) => [...researchKeys.all, 'sources', params] as const,
  source: (sourceDocumentId: number) =>
    [...researchKeys.all, 'source', sourceDocumentId] as const,
  search: (params: ResearchSearchRequest) =>
    [...researchKeys.all, 'search', params] as const,
  passage: (sourceChunkId: number) =>
    [...researchKeys.all, 'passage', sourceChunkId] as const,
}
