import type { InteractionCitation } from '../../api/types/interactions'
import type { AssistantTurnExtras } from '../../features/cases/messageTurn'
import { CitationChip } from './CitationChip'
import { DisclosureBanner } from './DisclosureBanner'
import { FactsNeededList } from './FactsNeededList'
import { RetrievalStatusBanner } from './RetrievalStatusBanner'
import styles from './ConversationPanel.module.css'

export type DisplayMessage = {
  key: string
  id: number | string
  role: 'user' | 'assistant' | 'pending_user' | 'failed_user' | 'system'
  content: string
  extras?: AssistantTurnExtras
}

type Props = {
  message: DisplayMessage
  selectedCitationKey: string | null
  onSelectCitation: (
    messageKey: string,
    citationIndex: number,
    citation: InteractionCitation,
    chipElement: HTMLButtonElement | null,
  ) => void
  onRetryRetrieval?: () => void
  chipRefs?: Map<string, HTMLButtonElement | null>
}

export function MessageBubble({
  message,
  selectedCitationKey,
  onSelectCitation,
  onRetryRetrieval,
  chipRefs,
}: Props) {
  const isUser =
    message.role === 'user' ||
    message.role === 'pending_user' ||
    message.role === 'failed_user'
  const isAssistant = message.role === 'assistant'
  const isPending = message.role === 'pending_user'
  const isFailed = message.role === 'failed_user'
  const citations = message.extras?.citations ?? []

  return (
    <article
      className={`${styles.bubbleRow} ${isUser ? styles.bubbleRowUser : styles.bubbleRowAssistant}`}
      aria-label={
        isUser
          ? isFailed
            ? 'Failed steward message'
            : isPending
              ? 'Pending steward message'
              : 'Steward message'
          : 'Assistant message'
      }
    >
      <div className={styles.roleLabel}>
        {isUser ? 'Steward' : 'Assistant'}
        {isPending ? ' · sending' : ''}
        {isFailed ? ' · failed' : ''}
      </div>
      <div
        className={`${styles.bubble} ${isUser ? styles.bubbleUser : styles.bubbleAssistant} ${isPending ? styles.bubblePending : ''} ${isFailed ? styles.bubbleFailed : ''}`}
        role={isFailed ? 'alert' : undefined}
      >
        {isAssistant ? (
          <p className={`${styles.generatedText} generated-text`}>
            {message.content}
          </p>
        ) : (
          <p className={styles.generatedText}>{message.content}</p>
        )}
      </div>

      {isAssistant && message.extras ? (
        <>
          <RetrievalStatusBanner
            status={message.extras.retrieval_status}
            retrievalError={message.extras.retrieval_error}
            onRetry={
              message.extras.retrieval_status === 'failed' ||
              message.extras.retrieval_error
                ? onRetryRetrieval
                : undefined
            }
          />
          <DisclosureBanner disclosures={message.extras.disclosures} />
          <FactsNeededList factsNeeded={message.extras.facts_needed} />
          {citations.length > 0 ? (
            <div className={styles.chipRow} aria-label="Citations">
              {citations.map((citation, index) => {
                const chipKey = `${message.key}:${index}`
                return (
                  <CitationChip
                    key={chipKey}
                    citation={citation}
                    index={index}
                    selected={selectedCitationKey === chipKey}
                    buttonRef={(node) => {
                      chipRefs?.set(chipKey, node)
                    }}
                    onSelect={() => {
                      const node = chipRefs?.get(chipKey) ?? null
                      onSelectCitation(message.key, index, citation, node)
                    }}
                  />
                )
              })}
            </div>
          ) : null}
        </>
      ) : null}
    </article>
  )
}
