/** Browser-safe Sources Research contracts (W6 M9). */

export type ResearchUiStatus =
  | 'ok'
  | 'empty'
  | 'failed'
  | 'skipped'
  | 'partial'

export type ResearchSupportedFilter = {
  value: string
  label: string
}

export type ResearchMetaResponse = {
  source_types: ResearchSupportedFilter[]
  default_limit: number
  max_limit: number
  default_limit_per_source: number
  max_limit_per_source: number
  max_offset: number
  max_query_chars: number
  authority_notice: string
  boundary: string
}

export type ResearchPassageMetadata = {
  article?: string | null
  chapter?: string | null
  heading?: string | null
  page?: number | string | null
  section?: string | null
}

export type ResearchSearchRequest = {
  query: string
  source_types?: string[]
  source_ids?: string[]
  limit?: number
  limit_per_source?: number
  offset?: number
  domain?: string
}

export type ResearchSearchResultItem = {
  rank: number
  source_document_id: number
  canonical_source_id: string
  source_title: string
  source_type: string
  source_type_label: string
  source_chunk_id: number
  chunk_index: number
  page_number?: number | null
  section?: string | null
  article?: string | null
  heading?: string | null
  passage_text: string
  excerpt: string
  final_relevance_score: number
  normalized_score: number
  evidence_role: string
  retrieval_agent: string
  content_trust: string
  provenance: string
  metadata: ResearchPassageMetadata
}

export type ResearchFailure = {
  code: string
  message: string
  retriable: boolean
}

export type ResearchSearchResponse = {
  query: string
  retrieval_status: ResearchUiStatus
  retrieval_status_raw: string
  partial: boolean
  result_count: number
  total_matched: number
  limit: number
  offset: number
  limit_per_source: number
  results: ResearchSearchResultItem[]
  failures: ResearchFailure[]
  authority_notice: string
}

export type ResearchSourceSummary = {
  source_document_id: number
  canonical_source_id: string
  title: string
  source_type: string
  source_type_label: string
  is_current: boolean
  processing_status: string
  is_indexed: boolean
  official_page?: string | null
  version?: string | null
}

export type ResearchSourceListResponse = {
  count: number
  total: number
  limit: number
  offset: number
  sources: ResearchSourceSummary[]
  authority_notice: string
}

export type ResearchSourceDetail = {
  source_document_id: number
  canonical_source_id: string
  title: string
  source_type: string
  source_type_label: string
  is_current: boolean
  processing_status: string
  is_indexed: boolean
  official_page?: string | null
  version?: string | null
  content_type?: string | null
  chunk_count: number
  embedded_chunk_count: number
  authority_notice: string
}

export type ResearchPassageDetail = {
  source_chunk_id: number
  chunk_index: number
  source_document_id: number
  canonical_source_id: string
  source_title: string
  source_type: string
  source_type_label: string
  page_number?: number | null
  section_label?: string | null
  passage_text: string
  metadata: ResearchPassageMetadata
  processing_status: string
  is_indexed: boolean
  authority_notice: string
}

export type ResearchSearchParams = {
  q: string
  sourceType: string
  sourceId: string
  limit: number
  offset: number
  selectedChunkId: number | null
}
