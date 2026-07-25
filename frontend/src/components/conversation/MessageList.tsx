import type { InteractionCitation } from '../../api/types/interactions'
import { MessageBubble, type DisplayMessage } from './MessageBubble'
import styles from './ConversationPanel.module.css'

type Props = {
  messages: DisplayMessage[]
  selectedCitationKey: string | null
  onSelectCitation: (
    messageKey: string,
    citationIndex: number,
    citation: InteractionCitation,
    chipElement: HTMLButtonElement | null,
  ) => void
  onRetryRetrieval?: () => void
  chipRefs?: Map<string, HTMLButtonElement | null>
  liveAnnouncement?: string
}

export function MessageList({
  messages,
  selectedCitationKey,
  onSelectCitation,
  onRetryRetrieval,
  chipRefs,
  liveAnnouncement,
}: Props) {
  return (
    <div
      className={styles.thread}
      role="log"
      aria-label="Case conversation"
      aria-relevant="additions"
    >
      {messages.map((message) => (
        <MessageBubble
          key={message.key}
          message={message}
          selectedCitationKey={selectedCitationKey}
          onSelectCitation={onSelectCitation}
          onRetryRetrieval={onRetryRetrieval}
          chipRefs={chipRefs}
        />
      ))}
      <div className={styles.liveRegion} aria-live="polite" aria-atomic="true">
        {liveAnnouncement}
      </div>
    </div>
  )
}
