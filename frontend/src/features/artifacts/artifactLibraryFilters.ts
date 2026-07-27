import type {
  ArtifactSortOrder,
  ArtifactTypeFilter,
  CaseSavedArtifactSummary,
  HistoryOrder,
} from '../../api/types/artifacts'

export type ArtifactLibraryUrlState = {
  type: ArtifactTypeFilter
  sort: ArtifactSortOrder
  artifact: string | null
  historyOrder: HistoryOrder
  timelineOrder: HistoryOrder
}

const TYPE_VALUES = new Set<ArtifactTypeFilter>([
  'all',
  'analysis_report',
  'grievance_form',
])

const SORT_VALUES = new Set<ArtifactSortOrder>(['newest', 'oldest'])

const ORDER_VALUES = new Set<HistoryOrder>(['oldest_first', 'newest_first'])

export function parseArtifactLibraryState(
  searchParams: URLSearchParams,
): ArtifactLibraryUrlState {
  const typeRaw = searchParams.get('type')
  const sortRaw = searchParams.get('sort')
  const historyRaw = searchParams.get('historyOrder')
  const timelineRaw = searchParams.get('timelineOrder')
  const artifact = searchParams.get('artifact')?.trim() || null

  return {
    type:
      typeRaw && TYPE_VALUES.has(typeRaw as ArtifactTypeFilter)
        ? (typeRaw as ArtifactTypeFilter)
        : 'all',
    sort:
      sortRaw && SORT_VALUES.has(sortRaw as ArtifactSortOrder)
        ? (sortRaw as ArtifactSortOrder)
        : 'newest',
    artifact,
    historyOrder:
      historyRaw && ORDER_VALUES.has(historyRaw as HistoryOrder)
        ? (historyRaw as HistoryOrder)
        : 'newest_first',
    timelineOrder:
      timelineRaw && ORDER_VALUES.has(timelineRaw as HistoryOrder)
        ? (timelineRaw as HistoryOrder)
        : 'newest_first',
  }
}

export function applyArtifactLibraryState(
  searchParams: URLSearchParams,
  next: Partial<ArtifactLibraryUrlState>,
): URLSearchParams {
  const merged = new URLSearchParams(searchParams)
  const current = parseArtifactLibraryState(searchParams)
  const state = { ...current, ...next }

  if (state.type === 'all') {
    merged.delete('type')
  } else {
    merged.set('type', state.type)
  }

  if (state.sort === 'newest') {
    merged.delete('sort')
  } else {
    merged.set('sort', state.sort)
  }

  if (state.artifact) {
    merged.set('artifact', state.artifact)
  } else {
    merged.delete('artifact')
  }

  if (state.historyOrder === 'newest_first') {
    merged.delete('historyOrder')
  } else {
    merged.set('historyOrder', state.historyOrder)
  }

  if (state.timelineOrder === 'newest_first') {
    merged.delete('timelineOrder')
  } else {
    merged.set('timelineOrder', state.timelineOrder)
  }

  return merged
}

export function sortArtifacts(
  artifacts: CaseSavedArtifactSummary[],
  sort: ArtifactSortOrder,
): CaseSavedArtifactSummary[] {
  const copy = [...artifacts]
  copy.sort((a, b) => {
    const aTime = Date.parse(a.saved_at)
    const bTime = Date.parse(b.saved_at)
    if (Number.isNaN(aTime) || Number.isNaN(bTime)) {
      return a.version_number - b.version_number
    }
    return sort === 'newest' ? bTime - aTime : aTime - bTime
  })
  return copy
}

export function artifactTypeLabel(type: string | null | undefined): string {
  if (type === 'analysis_report') return 'Analysis report'
  if (type === 'grievance_form') return 'Grievance form'
  return type || 'Artifact'
}

export function pdfStatusLabel(status: string | null | undefined): string {
  if (status === 'ready') return 'PDF ready'
  if (status === 'failed') return 'PDF failed'
  if (status === 'pending') return 'PDF pending'
  return status ? `PDF ${status}` : 'PDF status unknown'
}

export function formatTimestamp(value: string | null | undefined): string {
  if (!value) return '—'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  return date.toLocaleString(undefined, {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
    hour: 'numeric',
    minute: '2-digit',
  })
}

export function shortArtifactId(uuid: string): string {
  if (uuid.length <= 12) return uuid
  return `${uuid.slice(0, 8)}…`
}

/** Compatible comparison requires same artifact_type and distinct UUIDs. */
export function canCompareArtifacts(
  left: CaseSavedArtifactSummary | null | undefined,
  right: CaseSavedArtifactSummary | null | undefined,
): { ok: true } | { ok: false; reason: string } {
  if (!left || !right) {
    return { ok: false, reason: 'Select two official artifacts to compare.' }
  }
  if (left.artifact_uuid === right.artifact_uuid) {
    return {
      ok: false,
      reason: 'Select two different artifacts. An artifact cannot be compared to itself.',
    }
  }
  if (left.artifact_type !== right.artifact_type) {
    return {
      ok: false,
      reason:
        'Compared artifacts must share the same type (both analysis reports or both grievance forms).',
    }
  }
  return { ok: true }
}
