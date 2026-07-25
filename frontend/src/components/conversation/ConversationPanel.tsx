import { useEffect, useId, useMemo, useRef, useState } from 'react'
import { ApiError } from '../../api/client'
import type { InteractionCitation } from '../../api/types/interactions'
import { extrasFromMessageMetadata } from '../../features/cases/messageTurn'
import { useCaseMessagesQuery } from '../../features/cases/useCaseMessagesQuery'
import {
  InteractionRejectedError,
  useSubmitInteractionMutation,
} from '../../features/cases/useSubmitInteractionMutation'
import { CitationPanel } from './CitationPanel'
import { ConversationComposer } from './ConversationComposer'
import type { DisplayMessage } from './MessageBubble'
import { MessageList } from './MessageList'
import styles from './ConversationPanel.module.css'

type Props = {
  caseUuid: string
  caseStatus?: string | null
}

type PendingTurn = {
  clientId: string
  content: string
  status: 'pending' | 'failed'
  errorMessage?: string
}

type SelectedCitation = {
  key: string
  citation: InteractionCitation
}

function isTerminalStatus(status: string | null | undefined): boolean {
  return status === 'closed' || status === 'settled' || status === 'archived'
}

export function ConversationPanel({ caseUuid, caseStatus }: Props) {
  const headingId = useId()
  const messagesQuery = useCaseMessagesQuery(caseUuid)
  const mutation = useSubmitInteractionMutation()
  const [draft, setDraft] = useState('')
  const [selectedAssetUuids, setSelectedAssetUuids] = useState<string[]>([])
  const [pending, setPending] = useState<PendingTurn | null>(null)
  const [selected, setSelected] = useState<SelectedCitation | null>(null)
  const [liveAnnouncement, setLiveAnnouncement] = useState('')
  const [researchElapsed, setResearchElapsed] = useState(false)
  const chipRefs = useRef(new Map<string, HTMLButtonElement | null>())
  const lastChipRef = useRef<HTMLButtonElement | null>(null)
  const abortRef = useRef<AbortController | null>(null)
  const caseUuidRef = useRef(caseUuid)
  const selectedAssetsRef = useRef<string[]>([])

  useEffect(() => {
    caseUuidRef.current = caseUuid
    setDraft('')
    setSelectedAssetUuids([])
    selectedAssetsRef.current = []
    setPending(null)
    setSelected(null)
    setLiveAnnouncement('')
    setResearchElapsed(false)
    abortRef.current?.abort()
    abortRef.current = null
    chipRefs.current.clear()
  }, [caseUuid])

  useEffect(() => {
    selectedAssetsRef.current = selectedAssetUuids
  }, [selectedAssetUuids])

  useEffect(() => {
    if (!pending || pending.status !== 'pending') {
      setResearchElapsed(false)
      return
    }
    const timer = window.setTimeout(() => setResearchElapsed(true), 2000)
    return () => window.clearTimeout(timer)
  }, [pending])

  const displayMessages: DisplayMessage[] = useMemo(() => {
    const serverMessages = messagesQuery.data?.messages ?? []
    const rows: DisplayMessage[] = serverMessages.map((message) => {
      const role =
        message.role === 'assistant'
          ? 'assistant'
          : message.role === 'user'
            ? 'user'
            : 'system'
      return {
        key: `msg-${message.id}`,
        id: message.id,
        role,
        content: message.content,
        extras:
          role === 'assistant'
            ? extrasFromMessageMetadata(message.metadata)
            : undefined,
      }
    })

    if (pending) {
      rows.push({
        key: pending.clientId,
        id: pending.clientId,
        role: pending.status === 'failed' ? 'failed_user' : 'pending_user',
        content: pending.content,
      })
    }

    return rows.filter((row) => row.role !== 'system')
  }, [messagesQuery.data?.messages, pending])

  const terminal = isTerminalStatus(caseStatus)
  const submitting = pending?.status === 'pending' || mutation.isPending

  async function sendMessage(text: string, uploadRefs: string[]) {
    const trimmed = text.trim()
    if (!trimmed || submitting || terminal) {
      return
    }

    const clientId = `pending-${Date.now()}`
    const refsForRequest = [...uploadRefs]
    setPending({ clientId, content: trimmed, status: 'pending' })
    setDraft('')
    abortRef.current?.abort()
    const controller = new AbortController()
    abortRef.current = controller
    const requestCaseUuid = caseUuid

    try {
      const result = await mutation.mutateAsync({
        caseUuid: requestCaseUuid,
        request: {
          message: trimmed,
          source: 'manual_ui',
          ...(refsForRequest.length > 0
            ? { upload_refs: refsForRequest }
            : {}),
        },
        signal: controller.signal,
      })

      if (caseUuidRef.current !== requestCaseUuid) {
        return
      }

      setPending(null)
      setSelectedAssetUuids([])
      selectedAssetsRef.current = []
      const assistantId = result.response.assistant_message?.id
      if (assistantId != null && result.assistantExtras.citations.length > 0) {
        const first = result.assistantExtras.citations[0]
        setSelected({
          key: `msg-${assistantId}:0`,
          citation: first,
        })
      } else if (assistantId != null) {
        setSelected(null)
      }

      setLiveAnnouncement('Assistant response ready.')
    } catch (error) {
      if (error instanceof DOMException && error.name === 'AbortError') {
        return
      }
      if (caseUuidRef.current !== requestCaseUuid) {
        return
      }

      const message =
        error instanceof InteractionRejectedError
          ? error.message
          : error instanceof ApiError
            ? error.message
            : 'Unable to send the message.'

      setPending({
        clientId,
        content: trimmed,
        status: 'failed',
        errorMessage: message,
      })
      setDraft(trimmed)
      // Preserve attachment refs after recoverable failure.
      setSelectedAssetUuids(refsForRequest)
      selectedAssetsRef.current = refsForRequest
    }
  }

  function handleRetryFailed() {
    if (!pending || pending.status !== 'failed') {
      return
    }
    void sendMessage(pending.content, selectedAssetsRef.current)
  }

  function handleSelectCitation(
    messageKey: string,
    citationIndex: number,
    citation: InteractionCitation,
    chipElement: HTMLButtonElement | null,
  ) {
    const key = `${messageKey}:${citationIndex}`
    lastChipRef.current = chipElement
    setSelected({ key, citation })
  }

  function handleClearSelection() {
    setSelected(null)
    lastChipRef.current?.focus()
  }

  return (
    <div className={styles.layout}>
      <section
        className={styles.conversation}
        aria-labelledby={headingId}
        aria-busy={submitting || messagesQuery.isLoading || undefined}
      >
        <header className={styles.header}>
          <h2 id={headingId} className={styles.heading}>
            Conversation
          </h2>
          <p className={styles.subhead}>
            Case-scoped research chat. The application manages workflow; the
            steward manages the grievance.
          </p>
        </header>

        {messagesQuery.isLoading && !messagesQuery.data ? (
          <div className={styles.skeleton} role="status">
            Loading conversation…
          </div>
        ) : null}

        {messagesQuery.isError && !messagesQuery.data ? (
          <div className={styles.errorBox} role="alert">
            <p>
              {messagesQuery.error instanceof ApiError
                ? messagesQuery.error.message
                : 'Unable to load conversation history.'}
            </p>
            <button
              type="button"
              className={styles.retryButton}
              onClick={() => {
                void messagesQuery.refetch()
              }}
            >
              Retry
            </button>
          </div>
        ) : null}

        {messagesQuery.data && displayMessages.length === 0 && !pending ? (
          <div className={styles.empty} role="status">
            No conversation yet. Send a question to retrieve authorities and
            draft a case-scoped answer.
          </div>
        ) : null}

        {displayMessages.length > 0 ? (
          <MessageList
            messages={displayMessages}
            selectedCitationKey={selected?.key ?? null}
            onSelectCitation={handleSelectCitation}
            onRetryRetrieval={
              pending?.status === 'failed' ? handleRetryFailed : undefined
            }
            chipRefs={chipRefs.current}
            liveAnnouncement={liveAnnouncement}
          />
        ) : null}

        {submitting ? (
          <p className={styles.researching} role="status">
            {researchElapsed
              ? 'Retrieving sources and drafting an answer…'
              : 'Researching authorities…'}
          </p>
        ) : null}

        {pending?.status === 'failed' ? (
          <div className={styles.errorBox} role="alert">
            <p>{pending.errorMessage ?? 'Message failed to send.'}</p>
            <button
              type="button"
              className={styles.retryButton}
              onClick={handleRetryFailed}
            >
              Retry
            </button>
          </div>
        ) : null}

        <ConversationComposer
          caseUuid={caseUuid}
          value={draft}
          selectedAssetUuids={selectedAssetUuids}
          pending={submitting}
          readOnlyReason={
            terminal
              ? 'This case is closed. Reopen it before continuing the conversation.'
              : null
          }
          onChange={setDraft}
          onSelectedAssetsChange={setSelectedAssetUuids}
          onSubmit={() => {
            void sendMessage(draft, selectedAssetUuids)
          }}
        />
      </section>

      <CitationPanel
        citation={selected?.citation ?? null}
        onClose={selected ? handleClearSelection : undefined}
      />
    </div>
  )
}
