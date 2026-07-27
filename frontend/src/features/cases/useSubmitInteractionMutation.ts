import { useMutation, useQueryClient } from '@tanstack/react-query'
import { submitCaseInteraction } from '../../api/interactions'
import type {
  CaseInteractionRequest,
  CaseInteractionResponse,
} from '../../api/types/interactions'
import type { ListCaseMessagesResponse } from '../../api/types/messages'
import { MESSAGES_DEFAULT_LIMIT } from '../../api/types/messages'
import {
  extrasFromMessageMetadata,
  mergeMessagesById,
  messageFromSummary,
  type AssistantTurnExtras,
} from './messageTurn'
import { messageKeys, workspaceKeys } from './savedCaseActions'

export class InteractionRejectedError extends Error {
  readonly response: CaseInteractionResponse

  constructor(response: CaseInteractionResponse) {
    super(response.message || 'Interaction was not completed.')
    this.name = 'InteractionRejectedError'
    this.response = response
  }
}

export type SubmitInteractionInput = {
  caseUuid: string
  request: CaseInteractionRequest
  signal?: AbortSignal
}

export type SubmitInteractionResult = {
  response: CaseInteractionResponse
  assistantExtras: AssistantTurnExtras
}

function defaultMessagesPage(
  caseUuid: string,
): ListCaseMessagesResponse {
  return {
    case_uuid: caseUuid,
    count: 0,
    total: 0,
    limit: MESSAGES_DEFAULT_LIMIT,
    offset: 0,
    order: 'oldest_first',
    has_more: false,
    messages: [],
  }
}

export function useSubmitInteractionMutation() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: async ({
      caseUuid,
      request,
      signal,
    }: SubmitInteractionInput): Promise<SubmitInteractionResult> => {
      const response = await submitCaseInteraction(caseUuid, request, signal)
      if (response.status !== 'completed') {
        throw new InteractionRejectedError(response)
      }
      const fromMeta = extrasFromMessageMetadata(
        response.assistant_message?.metadata ?? null,
      )
      const assistantExtras: AssistantTurnExtras = {
        citations:
          response.citations && response.citations.length > 0
            ? response.citations
            : fromMeta.citations,
        disclosures:
          response.disclosures && response.disclosures.length > 0
            ? response.disclosures
            : fromMeta.disclosures,
        facts_needed:
          response.facts_needed && response.facts_needed.length > 0
            ? response.facts_needed
            : fromMeta.facts_needed,
        retrieval_status: response.retrieval_status ?? fromMeta.retrieval_status,
        retrieval_error:
          response.retrieval_error ?? fromMeta.retrieval_error,
      }
      return { response, assistantExtras }
    },
    onSuccess: (result, variables) => {
      const { response, assistantExtras } = result
      const pagination = {
        limit: MESSAGES_DEFAULT_LIMIT,
        offset: 0,
        order: 'oldest_first' as const,
      }
      const key = messageKeys.list(variables.caseUuid, pagination)
      const incoming = [
        response.user_message
          ? messageFromSummary(response.user_message)
          : null,
        response.assistant_message
          ? messageFromSummary({
              ...response.assistant_message,
              metadata: {
                ...(response.assistant_message.metadata ?? {}),
                citations: assistantExtras.citations,
                disclosures: assistantExtras.disclosures,
                facts_needed: assistantExtras.facts_needed,
                retrieval_status: assistantExtras.retrieval_status,
                retrieval_error: assistantExtras.retrieval_error,
              },
            })
          : null,
      ].filter((message): message is NonNullable<typeof message> => !!message)

      queryClient.setQueryData<ListCaseMessagesResponse>(key, (current) => {
        const base = current ?? defaultMessagesPage(variables.caseUuid)
        const messages = mergeMessagesById(base.messages, incoming)
        return {
          ...base,
          case_uuid: variables.caseUuid,
          messages,
          count: messages.length,
          total: Math.max(base.total, messages.length),
          has_more: base.has_more,
        }
      })

      if (response.case_memory_update_status === 'updated') {
        void queryClient.invalidateQueries({
          queryKey: workspaceKeys.detail(variables.caseUuid),
        })
      }
    },
  })
}
