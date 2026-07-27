import type { ResearchSearchParams } from '../../api/types/research'

export const DEFAULT_RESEARCH_LIMIT = 12
export const MAX_RESEARCH_LIMIT = 24

export function parseResearchSearchParams(
  searchParams: URLSearchParams,
): ResearchSearchParams {
  const q = searchParams.get('q')?.trim() ?? ''
  const sourceType = (searchParams.get('sourceType') ?? '').trim().toUpperCase()
  const sourceId = (searchParams.get('sourceId') ?? '').trim()
  const limitRaw = Number(searchParams.get('limit') ?? DEFAULT_RESEARCH_LIMIT)
  const offsetRaw = Number(searchParams.get('offset') ?? 0)
  const selectedRaw = searchParams.get('chunk')
  const selectedChunkId =
    selectedRaw && /^\d+$/.test(selectedRaw) ? Number(selectedRaw) : null

  const limit = Number.isFinite(limitRaw)
    ? Math.min(MAX_RESEARCH_LIMIT, Math.max(1, Math.trunc(limitRaw)))
    : DEFAULT_RESEARCH_LIMIT
  const offset = Number.isFinite(offsetRaw)
    ? Math.min(200, Math.max(0, Math.trunc(offsetRaw)))
    : 0

  return {
    q,
    sourceType,
    sourceId,
    limit,
    offset,
    selectedChunkId,
  }
}

export function buildResearchSearchParams(
  current: URLSearchParams,
  next: Partial<ResearchSearchParams>,
): URLSearchParams {
  const merged = new URLSearchParams(current)
  const parsed = { ...parseResearchSearchParams(current), ...next }

  if (parsed.q) {
    merged.set('q', parsed.q)
  } else {
    merged.delete('q')
  }

  if (parsed.sourceType) {
    merged.set('sourceType', parsed.sourceType)
  } else {
    merged.delete('sourceType')
  }

  if (parsed.sourceId) {
    merged.set('sourceId', parsed.sourceId)
  } else {
    merged.delete('sourceId')
  }

  if (parsed.limit !== DEFAULT_RESEARCH_LIMIT) {
    merged.set('limit', String(parsed.limit))
  } else {
    merged.delete('limit')
  }

  if (parsed.offset > 0) {
    merged.set('offset', String(parsed.offset))
  } else {
    merged.delete('offset')
  }

  if (parsed.selectedChunkId != null) {
    merged.set('chunk', String(parsed.selectedChunkId))
  } else {
    merged.delete('chunk')
  }

  return merged
}

export function clearResearchSearchParams(
  current: URLSearchParams,
): URLSearchParams {
  const merged = new URLSearchParams(current)
  ;['q', 'sourceType', 'sourceId', 'limit', 'offset', 'chunk'].forEach((key) => {
    merged.delete(key)
  })
  return merged
}
