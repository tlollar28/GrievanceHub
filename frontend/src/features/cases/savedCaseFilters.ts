import type {
  ListSavedCasesParams,
  SavedCaseOrder,
  SavedCaseStatusFilter,
  StepType,
} from '../../api/types/savedCases'

export const DEFAULT_CASES_LIMIT = 25
export const DEFAULT_DASHBOARD_LIMIT = 10

const STATUS_VALUES: SavedCaseStatusFilter[] = [
  'all',
  'open',
  'closed',
  'reopened',
  'appealed',
  'settled',
  'archived',
]

const STEP_VALUES: StepType[] = [
  'step_1_initial',
  'step_2_appeal',
  'step_3_appeal',
]

const ORDER_VALUES: SavedCaseOrder[] = ['newest_first', 'oldest_first']

function parsePositiveInt(
  value: string | null,
  fallback: number,
  min: number,
  max: number,
): number {
  if (!value) {
    return fallback
  }
  const parsed = Number.parseInt(value, 10)
  if (!Number.isFinite(parsed)) {
    return fallback
  }
  return Math.min(max, Math.max(min, parsed))
}

export function parseSavedCaseFilters(
  searchParams: URLSearchParams,
  defaults: { limit?: number } = {},
): ListSavedCasesParams {
  const statusRaw = searchParams.get('status')
  const status = STATUS_VALUES.includes(statusRaw as SavedCaseStatusFilter)
    ? (statusRaw as SavedCaseStatusFilter)
    : 'all'

  const stepRaw = searchParams.get('step')
  const step = STEP_VALUES.includes(stepRaw as StepType)
    ? (stepRaw as StepType)
    : null

  const orderRaw = searchParams.get('order')
  const order = ORDER_VALUES.includes(orderRaw as SavedCaseOrder)
    ? (orderRaw as SavedCaseOrder)
    : 'newest_first'

  const search = searchParams.get('search')?.trim() || null
  const limit = parsePositiveInt(
    searchParams.get('limit'),
    defaults.limit ?? DEFAULT_CASES_LIMIT,
    1,
    100,
  )
  const offset = parsePositiveInt(searchParams.get('offset'), 0, 0, 1_000_000)

  return {
    status,
    step,
    search,
    order,
    limit,
    offset,
  }
}

export function savedCaseFiltersToSearchParams(
  filters: ListSavedCasesParams,
  defaults: { limit?: number } = {},
): URLSearchParams {
  const params = new URLSearchParams()
  const defaultLimit = defaults.limit ?? DEFAULT_CASES_LIMIT

  if (filters.status && filters.status !== 'all') {
    params.set('status', filters.status)
  }
  if (filters.step) {
    params.set('step', filters.step)
  }
  if (filters.search) {
    params.set('search', filters.search)
  }
  if (filters.order && filters.order !== 'newest_first') {
    params.set('order', filters.order)
  }
  if (filters.limit != null && filters.limit !== defaultLimit) {
    params.set('limit', String(filters.limit))
  }
  if (filters.offset != null && filters.offset > 0) {
    params.set('offset', String(filters.offset))
  }

  return params
}

export function formatStepType(step: StepType | null | undefined): string {
  switch (step) {
    case 'step_1_initial':
      return 'Step 1'
    case 'step_2_appeal':
      return 'Step 2'
    case 'step_3_appeal':
      return 'Step 3'
    default:
      return '—'
  }
}

export function formatWorkspaceStatus(
  status: string | null | undefined,
): string {
  if (!status) {
    return 'Unknown'
  }
  return status.charAt(0).toUpperCase() + status.slice(1)
}

export function formatDateTime(value: string | null | undefined): string {
  if (!value) {
    return '—'
  }
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) {
    return value
  }
  return new Intl.DateTimeFormat(undefined, {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
    hour: 'numeric',
    minute: '2-digit',
  }).format(date)
}

export function caseDisplayTitle(summary: {
  title?: string | null
  issue_summary?: string | null
  case_number?: string | null
}): string {
  return (
    summary.title?.trim() ||
    summary.issue_summary?.trim() ||
    (summary.case_number
      ? `Case ${summary.case_number}`
      : 'Untitled case')
  )
}
