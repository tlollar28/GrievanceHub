/**
 * Hand-mirrored from CaseService.list_case_messages
 * (GET /cases/{case_uuid}/messages).
 * OpenAPI omits a response_model for this route.
 */

export type MessageOrder = 'oldest_first' | 'newest_first'

export type CaseMessage = {
  id: number
  role: string
  content: string
  metadata: Record<string, unknown> | null
  created_at: string | null
}

export type ListCaseMessagesParams = {
  limit?: number
  offset?: number
  order?: MessageOrder
}

export type ListCaseMessagesResponse = {
  case_uuid: string
  count: number
  total: number
  limit: number
  offset: number
  order: MessageOrder
  has_more: boolean
  messages: CaseMessage[]
}

/** Backend defaults from CaseService. */
export const MESSAGES_DEFAULT_LIMIT = 50
export const MESSAGES_MAX_LIMIT = 100
