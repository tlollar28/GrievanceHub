import { apiRequest } from './client'
import type {
  ListCaseMessagesParams,
  ListCaseMessagesResponse,
} from './types/messages'
import { MESSAGES_DEFAULT_LIMIT } from './types/messages'

function buildMessagesQuery(params: ListCaseMessagesParams = {}): string {
  const searchParams = new URLSearchParams()
  searchParams.set('limit', String(params.limit ?? MESSAGES_DEFAULT_LIMIT))
  searchParams.set('offset', String(params.offset ?? 0))
  searchParams.set('order', params.order ?? 'oldest_first')
  return searchParams.toString()
}

/** GET /cases/{case_uuid}/messages — paginated case-scoped history. */
export function listCaseMessages(
  caseUuid: string,
  params: ListCaseMessagesParams = {},
  signal?: AbortSignal,
): Promise<ListCaseMessagesResponse> {
  const query = buildMessagesQuery(params)
  return apiRequest<ListCaseMessagesResponse>(
    `/cases/${caseUuid}/messages?${query}`,
    { signal },
  )
}
