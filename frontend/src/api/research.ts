import { apiRequest } from './client'
import type {
  ResearchMetaResponse,
  ResearchPassageDetail,
  ResearchSearchRequest,
  ResearchSearchResponse,
  ResearchSourceDetail,
  ResearchSourceListResponse,
} from './types/research'

/** Typed clients for the browser-safe `/research/*` boundary. */

export function fetchResearchMeta(signal?: AbortSignal): Promise<ResearchMetaResponse> {
  return apiRequest<ResearchMetaResponse>('/research/meta', { signal })
}

export function searchResearchSources(
  body: ResearchSearchRequest,
  signal?: AbortSignal,
): Promise<ResearchSearchResponse> {
  return apiRequest<ResearchSearchResponse>('/research/search', {
    method: 'POST',
    body,
    signal,
  })
}

export function fetchResearchSources(
  params: {
    limit?: number
    offset?: number
    source_type?: string
  } = {},
  signal?: AbortSignal,
): Promise<ResearchSourceListResponse> {
  const search = new URLSearchParams()
  if (params.limit != null) search.set('limit', String(params.limit))
  if (params.offset != null) search.set('offset', String(params.offset))
  if (params.source_type) search.set('source_type', params.source_type)
  const qs = search.toString()
  return apiRequest<ResearchSourceListResponse>(
    `/research/sources${qs ? `?${qs}` : ''}`,
    { signal },
  )
}

export function fetchResearchSourceDetail(
  sourceDocumentId: number,
  signal?: AbortSignal,
): Promise<ResearchSourceDetail> {
  return apiRequest<ResearchSourceDetail>(
    `/research/sources/${sourceDocumentId}`,
    { signal },
  )
}

export function fetchResearchPassage(
  sourceChunkId: number,
  signal?: AbortSignal,
): Promise<ResearchPassageDetail> {
  return apiRequest<ResearchPassageDetail>(
    `/research/passages/${sourceChunkId}`,
    { signal },
  )
}
