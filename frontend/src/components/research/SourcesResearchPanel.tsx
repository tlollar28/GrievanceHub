import { useEffect, useMemo, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { ApiError } from '../../api/client'
import type { ResearchSearchRequest } from '../../api/types/research'
import {
  buildResearchSearchParams,
  clearResearchSearchParams,
  DEFAULT_RESEARCH_LIMIT,
  parseResearchSearchParams,
} from '../../features/research/researchSearchParams'
import { useResearchMetaQuery } from '../../features/research/useResearchMetaQuery'
import { useResearchSearchQuery } from '../../features/research/useResearchSearchQuery'
import { AuthorityEvidenceDistinctionNotice } from './AuthorityEvidenceDistinctionNotice'
import { RetrievalStatusNotice } from './RetrievalStatusNotice'
import { SourceDetailDialog } from './SourceDetailDialog'
import { SourceSearchForm, type SourceSearchFormValues } from './SourceSearchForm'
import { SourceResultsList } from './SourceResultsList'
import styles from './SourcesResearch.module.css'

type Props = {
  caseUuid: string
}

export function SourcesResearchPanel({ caseUuid }: Props) {
  const [searchParams, setSearchParams] = useSearchParams()
  const urlState = useMemo(
    () => parseResearchSearchParams(searchParams),
    [searchParams],
  )
  const metaQuery = useResearchMetaQuery()
  const [draft, setDraft] = useState<SourceSearchFormValues>({
    query: urlState.q,
    sourceType: urlState.sourceType,
    sourceId: urlState.sourceId,
    limit: urlState.limit,
  })
  const [submitted, setSubmitted] = useState(Boolean(urlState.q))

  useEffect(() => {
    setDraft({
      query: urlState.q,
      sourceType: urlState.sourceType,
      sourceId: urlState.sourceId,
      limit: urlState.limit,
    })
    setSubmitted(Boolean(urlState.q))
  }, [
    caseUuid,
    urlState.q,
    urlState.sourceType,
    urlState.sourceId,
    urlState.limit,
    urlState.offset,
    urlState.selectedChunkId,
  ])

  const request: ResearchSearchRequest | null = useMemo(() => {
    if (!submitted || !urlState.q.trim()) {
      return null
    }
    return {
      query: urlState.q.trim(),
      source_types: urlState.sourceType ? [urlState.sourceType] : [],
      source_ids: urlState.sourceId ? [urlState.sourceId] : [],
      limit: urlState.limit,
      offset: urlState.offset,
      limit_per_source: 3,
      domain: 'auto',
    }
  }, [
    submitted,
    urlState.q,
    urlState.sourceType,
    urlState.sourceId,
    urlState.limit,
    urlState.offset,
  ])

  const searchQuery = useResearchSearchQuery(request, submitted)

  const selected =
    searchQuery.data?.results.find(
      (item) => item.source_chunk_id === urlState.selectedChunkId,
    ) ?? null

  useEffect(() => {
    if (
      urlState.selectedChunkId != null &&
      searchQuery.isSuccess &&
      searchQuery.data &&
      !searchQuery.data.results.some(
        (item) => item.source_chunk_id === urlState.selectedChunkId,
      )
    ) {
      // Keep detail open via passage query even if not on current page.
      return
    }
  }, [urlState.selectedChunkId, searchQuery.isSuccess, searchQuery.data])

  function commitSearch(values: SourceSearchFormValues) {
    const query = values.query.trim()
    if (!query || searchQuery.isFetching) {
      return
    }
    setSubmitted(true)
    setSearchParams(
      buildResearchSearchParams(searchParams, {
        q: query,
        sourceType: values.sourceType,
        sourceId: values.sourceId.trim(),
        limit: values.limit || DEFAULT_RESEARCH_LIMIT,
        offset: 0,
        selectedChunkId: null,
      }),
      { replace: false },
    )
  }

  function clearAll() {
    setDraft({
      query: '',
      sourceType: '',
      sourceId: '',
      limit: DEFAULT_RESEARCH_LIMIT,
    })
    setSubmitted(false)
    setSearchParams(clearResearchSearchParams(searchParams), { replace: false })
  }

  const errorMessage =
    searchQuery.error instanceof ApiError
      ? searchQuery.error.message
      : searchQuery.isError
        ? 'Unable to complete authority research search.'
        : searchQuery.data?.failures[0]?.message

  const notice =
    metaQuery.data?.authority_notice ??
    searchQuery.data?.authority_notice ??
    undefined

  return (
    <div className={styles.panel} data-testid="sources-research-panel">
      <header className={styles.header}>
        <h2 className={styles.heading}>Sources Research</h2>
        <p className={styles.subhead}>
          Read-only inspection of the indexed authority corpus. This workspace
          section does not create messages, artifacts, workflow changes, or Case
          Memory updates.
        </p>
        <AuthorityEvidenceDistinctionNotice notice={notice} />
      </header>

      {metaQuery.isFetching ? (
        <p className={styles.status} role="status" aria-busy="true">
          {metaQuery.data
            ? 'Refreshing authority filter options…'
            : 'Loading authority filter options…'}
        </p>
      ) : null}
      {metaQuery.isError ? (
        <div className={styles.statusAlert} role="alert">
          <p>
            {metaQuery.error instanceof ApiError
              ? metaQuery.error.message
              : 'Unable to load authority filter options.'}
          </p>
          <button
            type="button"
            className={styles.buttonSecondary}
            onClick={() => void metaQuery.refetch()}
          >
            Retry
          </button>
        </div>
      ) : null}

      <SourceSearchForm
        values={draft}
        sourceTypes={metaQuery.data?.source_types ?? []}
        pending={searchQuery.isFetching}
        onChange={setDraft}
        onSubmit={() => commitSearch(draft)}
        onClear={clearAll}
      />

      <div>
        <RetrievalStatusNotice
          status={searchQuery.data?.retrieval_status ?? null}
          loading={searchQuery.isFetching}
          errorMessage={
            searchQuery.isError || searchQuery.data?.retrieval_status === 'failed'
              ? errorMessage
              : null
          }
          resultCount={searchQuery.data?.result_count}
          totalMatched={searchQuery.data?.total_matched}
          query={searchQuery.data?.query ?? urlState.q}
        />
      </div>

      <SourceResultsList
        results={searchQuery.data?.results ?? []}
        selectedChunkId={urlState.selectedChunkId}
        onSelect={(chunkId) => {
          setSearchParams(
            buildResearchSearchParams(searchParams, {
              selectedChunkId: chunkId,
            }),
            { replace: false },
          )
        }}
        offset={urlState.offset}
        limit={urlState.limit}
        totalMatched={searchQuery.data?.total_matched ?? 0}
        onPrevPage={() => {
          setSearchParams(
            buildResearchSearchParams(searchParams, {
              offset: Math.max(0, urlState.offset - urlState.limit),
              selectedChunkId: null,
            }),
          )
        }}
        onNextPage={() => {
          setSearchParams(
            buildResearchSearchParams(searchParams, {
              offset: urlState.offset + urlState.limit,
              selectedChunkId: null,
            }),
          )
        }}
      />

      <SourceDetailDialog
        selected={selected}
        selectedChunkId={urlState.selectedChunkId}
        onClose={() => {
          setSearchParams(
            buildResearchSearchParams(searchParams, {
              selectedChunkId: null,
            }),
          )
        }}
      />
    </div>
  )
}
