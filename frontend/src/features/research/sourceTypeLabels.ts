/** Friendly labels for verified authority source types. */

const SOURCE_TYPE_LABELS: Record<string, string> = {
  CONTRACT: 'National Agreement',
  CIM: 'Contract Interpretation Manual',
  SUPERVISOR_MANUAL: 'Supervisor Manual',
  ELM: 'Employee and Labor Relations Manual',
  LMOU: 'Local Memorandum of Understanding',
  ARBITRATION: 'Arbitration',
}

export function formatSourceTypeLabel(sourceType: string | null | undefined): string {
  const key = (sourceType ?? '').trim().toUpperCase()
  if (!key) {
    return 'Unknown source type'
  }
  if (SOURCE_TYPE_LABELS[key]) {
    return SOURCE_TYPE_LABELS[key]
  }
  return key
    .split('_')
    .filter(Boolean)
    .map((part) => part.charAt(0) + part.slice(1).toLowerCase())
    .join(' ')
}

export function formatRelevanceScore(score: number): string {
  if (!Number.isFinite(score)) {
    return 'n/a'
  }
  return `${Math.round(score * 100)}% relevance`
}
