import type { KnownFacts } from '../../api/types/cases'

export type FactRow = {
  id: string
  key: string
  value: string
}

let factRowCounter = 0

export function nextFactRowId(): string {
  factRowCounter += 1
  return `fact-row-${factRowCounter}`
}

export function factsToRows(facts: KnownFacts | null | undefined): FactRow[] {
  if (!facts || typeof facts !== 'object') {
    return []
  }
  return Object.entries(facts).map(([key, value]) => ({
    id: nextFactRowId(),
    key,
    value: serializeFactValue(value),
  }))
}

export function serializeFactValue(value: unknown): string {
  if (value === null || value === undefined) {
    return ''
  }
  if (typeof value === 'string') {
    return value
  }
  if (typeof value === 'number' || typeof value === 'boolean') {
    return String(value)
  }
  try {
    return JSON.stringify(value)
  } catch {
    return String(value)
  }
}

/** Build request known_facts; empty keys are dropped. Values stay strings. */
export function rowsToFacts(rows: FactRow[]): KnownFacts {
  const facts: KnownFacts = {}
  for (const row of rows) {
    const key = row.key.trim()
    if (!key) {
      continue
    }
    facts[key] = row.value
  }
  return facts
}

export function createEmptyFactRow(): FactRow {
  return { id: nextFactRowId(), key: '', value: '' }
}
