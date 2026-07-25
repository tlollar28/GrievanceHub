import type {
  InteractionCitation,
  RetrievalStatus,
} from '../../api/types/interactions'
import type { CaseMessage } from '../../api/types/messages'

export type AssistantTurnExtras = {
  citations: InteractionCitation[]
  disclosures: string[]
  facts_needed: string[]
  retrieval_status: RetrievalStatus | null
  retrieval_error: boolean
}

function asStringArray(value: unknown): string[] {
  if (!Array.isArray(value)) {
    return []
  }
  return value.filter((item): item is string => typeof item === 'string')
}

function asCitations(value: unknown): InteractionCitation[] {
  if (!Array.isArray(value)) {
    return []
  }
  return value.filter(
    (item): item is InteractionCitation =>
      !!item && typeof item === 'object' && !Array.isArray(item),
  )
}

function asRetrievalStatus(value: unknown): RetrievalStatus | null {
  if (
    value === 'ok' ||
    value === 'empty' ||
    value === 'failed' ||
    value === 'skipped'
  ) {
    return value
  }
  return null
}

/** Extract turn extras from persisted assistant message metadata. */
export function extrasFromMessageMetadata(
  metadata: Record<string, unknown> | null | undefined,
): AssistantTurnExtras {
  return {
    citations: asCitations(metadata?.citations),
    disclosures: asStringArray(metadata?.disclosures),
    facts_needed: asStringArray(metadata?.facts_needed),
    retrieval_status: asRetrievalStatus(metadata?.retrieval_status),
    retrieval_error: Boolean(metadata?.retrieval_error),
  }
}

export function messageFromSummary(summary: {
  id: number
  role: string
  content: string
  metadata?: Record<string, unknown> | null
  created_at?: string | null
}): CaseMessage {
  return {
    id: summary.id,
    role: summary.role,
    content: summary.content,
    metadata: summary.metadata ?? null,
    created_at: summary.created_at ?? null,
  }
}

/** Merge server messages without duplicating by id. */
export function mergeMessagesById(
  existing: CaseMessage[],
  incoming: CaseMessage[],
): CaseMessage[] {
  const byId = new Map<number, CaseMessage>()
  for (const message of existing) {
    byId.set(message.id, message)
  }
  for (const message of incoming) {
    byId.set(message.id, message)
  }
  return [...byId.values()].sort((a, b) => {
    const aTime = a.created_at ?? ''
    const bTime = b.created_at ?? ''
    if (aTime !== bTime) {
      return aTime.localeCompare(bTime)
    }
    return a.id - b.id
  })
}
