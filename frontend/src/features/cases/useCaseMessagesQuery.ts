import { useQuery } from '@tanstack/react-query'
import { listCaseMessages } from '../../api/messages'
import {
  MESSAGES_DEFAULT_LIMIT,
  type ListCaseMessagesParams,
} from '../../api/types/messages'
import { messageKeys } from './savedCaseActions'

const DEFAULT_PARAMS: Required<ListCaseMessagesParams> = {
  limit: MESSAGES_DEFAULT_LIMIT,
  offset: 0,
  order: 'oldest_first',
}

export function useCaseMessagesQuery(
  caseUuid: string,
  params: ListCaseMessagesParams = {},
  enabled = true,
) {
  const pagination = {
    limit: params.limit ?? DEFAULT_PARAMS.limit,
    offset: params.offset ?? DEFAULT_PARAMS.offset,
    order: params.order ?? DEFAULT_PARAMS.order,
  }

  return useQuery({
    queryKey: messageKeys.list(caseUuid, pagination),
    queryFn: ({ signal }) => listCaseMessages(caseUuid, pagination, signal),
    enabled: enabled && caseUuid.length > 0,
    placeholderData: (previous) => previous,
  })
}
