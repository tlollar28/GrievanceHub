import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { messageKeys, workspaceKeys } from '../features/cases/savedCaseActions'
import {
  OTHER_CASE_UUID,
  SAMPLE_CASE_UUID,
  installApiMock,
  jsonResponse,
  makeCitation,
  makeInteractionResponse,
  makeMessagesResponse,
  makeCaseMessage,
  makeWorkspace,
} from './savedCasesFixtures'
import { renderApp } from './testUtils'

function workspaceAndMessages(
  messages = makeMessagesResponse(),
  workspace = makeWorkspace(),
) {
  return installApiMock(
    (input, init) => {
      const url = String(input)
      if (url.includes(`/cases/${SAMPLE_CASE_UUID}/workspace`)) {
        return jsonResponse(workspace)
      }
      if (
        url.includes(`/cases/${SAMPLE_CASE_UUID}/messages`) &&
        (!init?.method || init.method === 'GET')
      ) {
        return jsonResponse(messages)
      }
      throw new Error(`Unexpected fetch: ${url}`)
    },
    { autoEmptyMessages: false },
  )
}

describe('W6 M3 Conversation and Retrieval', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
    vi.restoreAllMocks()
  })

  it('restores workspace and messages on conversation route', async () => {
    workspaceAndMessages(
      makeMessagesResponse([
        makeCaseMessage({ id: 1, role: 'user', content: 'First question' }),
        makeCaseMessage({
          id: 2,
          role: 'assistant',
          content: 'First answer',
          metadata: {
            citations: [makeCitation()],
            disclosures: ['Guidance only.'],
            facts_needed: [],
          },
          created_at: '2026-07-20T15:01:00Z',
        }),
      ]),
    )

    renderApp({
      initialEntries: [`/cases/${SAMPLE_CASE_UUID}/conversation`],
    })

    expect(
      await screen.findByRole('heading', { name: 'Overtime dispute' }),
    ).toBeInTheDocument()
    expect(
      await screen.findByRole('heading', { name: 'Conversation' }),
    ).toBeInTheDocument()
    expect(await screen.findByText('First question')).toBeInTheDocument()
    expect(screen.getByText('First answer')).toBeInTheDocument()
  })

  it('shows empty conversation state', async () => {
    workspaceAndMessages(makeMessagesResponse([]))

    renderApp({
      initialEntries: [`/cases/${SAMPLE_CASE_UUID}/conversation`],
    })

    expect(
      await screen.findByText(/No conversation yet/i),
    ).toBeInTheDocument()
  })

  it('shows messages loading state', async () => {
    installApiMock(
      (input) => {
        const url = String(input)
        if (url.includes('/workspace')) {
          return jsonResponse(makeWorkspace())
        }
        if (url.includes('/messages')) {
          return new Promise(() => {
            /* pending */
          })
        }
        throw new Error(`Unexpected fetch: ${url}`)
      },
      { autoEmptyMessages: false },
    )

    renderApp({
      initialEntries: [`/cases/${SAMPLE_CASE_UUID}/conversation`],
    })

    expect(await screen.findByText(/Loading conversation/i)).toBeInTheDocument()
  })

  it('shows messages failure with Retry', async () => {
    const user = userEvent.setup()
    let calls = 0
    installApiMock(
      (input) => {
        const url = String(input)
        if (url.includes('/workspace')) {
          return jsonResponse(makeWorkspace())
        }
        if (url.includes('/messages')) {
          calls += 1
          if (calls === 1) {
            return jsonResponse({ detail: 'Messages unavailable' }, 500)
          }
          return jsonResponse(
            makeMessagesResponse([
              makeCaseMessage({ content: 'Recovered message' }),
            ]),
          )
        }
        throw new Error(`Unexpected fetch: ${url}`)
      },
      { autoEmptyMessages: false },
    )

    renderApp({
      initialEntries: [`/cases/${SAMPLE_CASE_UUID}/conversation`],
    })

    expect(await screen.findByRole('alert')).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Retry' }))
    expect(await screen.findByText('Recovered message')).toBeInTheDocument()
  })

  it('renders messages in oldest-first order', async () => {
    workspaceAndMessages(
      makeMessagesResponse([
        makeCaseMessage({
          id: 1,
          content: 'Older steward note',
          created_at: '2026-07-20T14:00:00Z',
        }),
        makeCaseMessage({
          id: 2,
          role: 'assistant',
          content: 'Newer assistant reply',
          created_at: '2026-07-20T15:00:00Z',
          metadata: {},
        }),
      ]),
    )

    renderApp({
      initialEntries: [`/cases/${SAMPLE_CASE_UUID}/conversation`],
    })

    const log = await screen.findByRole('log', { name: 'Case conversation' })
    const text = log.textContent ?? ''
    expect(text.indexOf('Older steward note')).toBeLessThan(
      text.indexOf('Newer assistant reply'),
    )
  })

  it('blocks empty composer submission', async () => {
    const user = userEvent.setup()
    const fetchMock = workspaceAndMessages()

    renderApp({
      initialEntries: [`/cases/${SAMPLE_CASE_UUID}/conversation`],
    })
    await screen.findByRole('heading', { name: 'Conversation' })

    await user.click(screen.getByRole('button', { name: 'Send message' }))

    expect(
      fetchMock.mock.calls.some(([request, init]) =>
        String(request).includes('/interactions') && init?.method === 'POST',
      ),
    ).toBe(false)
  })

  it('sends exact verified interaction request and prevents duplicate send', async () => {
    const user = userEvent.setup()
    const bodies: unknown[] = []
    let resolveInteraction: ((value: Response) => void) | undefined

    installApiMock(
      (input, init) => {
        const url = String(input)
        if (url.includes('/workspace')) {
          return jsonResponse(makeWorkspace())
        }
        if (url.includes('/messages') && (!init?.method || init.method === 'GET')) {
          return jsonResponse(makeMessagesResponse([]))
        }
        if (url.includes('/interactions') && init?.method === 'POST') {
          bodies.push(JSON.parse(String(init.body)))
          return new Promise<Response>((resolve) => {
            resolveInteraction = resolve
          })
        }
        throw new Error(`Unexpected fetch: ${url}`)
      },
      { autoEmptyMessages: false },
    )

    renderApp({
      initialEntries: [`/cases/${SAMPLE_CASE_UUID}/conversation`],
    })
    await screen.findByRole('heading', { name: 'Conversation' })

    const composer = screen.getByLabelText('Message')
    await user.type(composer, 'What about Article 10?')
    await user.click(screen.getByRole('button', { name: 'Send message' }))

    expect(await screen.findByText(/Researching authorities/i)).toBeInTheDocument()
    expect(screen.getByText('What about Article 10?')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Send message' })).toBeDisabled()

    expect(bodies).toEqual([
      {
        message: 'What about Article 10?',
        source: 'manual_ui',
      },
    ])

    resolveInteraction!(
      jsonResponse(
        makeInteractionResponse({
          user_message: {
            id: 201,
            role: 'user',
            content: 'What about Article 10?',
            created_at: '2026-07-24T21:00:00Z',
          },
        }),
      ),
    )

    await waitFor(() => {
      expect(screen.queryByText(/Researching authorities/i)).not.toBeInTheDocument()
    })
    expect(bodies).toHaveLength(1)
  })

  it('reconciles persisted messages without duplicates after refetch', async () => {
    const user = userEvent.setup()
    let messageCalls = 0
    const interaction = makeInteractionResponse({
      case_memory_update_status: 'updated',
    })

    installApiMock(
      (input, init) => {
        const url = String(input)
        if (url.includes('/workspace')) {
          return jsonResponse(makeWorkspace())
        }
        if (url.includes('/messages') && (!init?.method || init.method === 'GET')) {
          messageCalls += 1
          if (messageCalls === 1) {
            return jsonResponse(makeMessagesResponse([]))
          }
          return jsonResponse(
            makeMessagesResponse([
              makeCaseMessage({
                id: interaction.user_message!.id,
                role: 'user',
                content: interaction.user_message!.content,
              }),
              makeCaseMessage({
                id: interaction.assistant_message!.id,
                role: 'assistant',
                content: interaction.assistant_message!.content,
                metadata: {
                  citations: interaction.citations,
                  disclosures: [],
                  facts_needed: [],
                },
              }),
            ]),
          )
        }
        if (url.includes('/interactions') && init?.method === 'POST') {
          return jsonResponse(interaction)
        }
        throw new Error(`Unexpected fetch: ${url}`)
      },
      { autoEmptyMessages: false },
    )

    const { queryClient } = renderApp({
      initialEntries: [`/cases/${SAMPLE_CASE_UUID}/conversation`],
    })
    await screen.findByRole('heading', { name: 'Conversation' })

    const invalidateSpy = vi.spyOn(queryClient, 'invalidateQueries')
    await user.type(screen.getByLabelText('Message'), 'What about Article 10?')
    await user.click(screen.getByRole('button', { name: 'Send message' }))

    expect(
      await screen.findByText(
        'Article 10 addresses overtime distribution by seniority.',
      ),
    ).toBeInTheDocument()

    await queryClient.refetchQueries({
      queryKey: messageKeys.list(SAMPLE_CASE_UUID, {
        limit: 50,
        offset: 0,
        order: 'oldest_first',
      }),
    })

    const answers = await screen.findAllByText(
      'Article 10 addresses overtime distribution by seniority.',
    )
    expect(answers).toHaveLength(1)

    expect(invalidateSpy).toHaveBeenCalledWith(
      expect.objectContaining({
        queryKey: workspaceKeys.detail(SAMPLE_CASE_UUID),
      }),
    )
  })

  it('preserves steward text and offers Retry on interaction failure', async () => {
    const user = userEvent.setup()
    let interactionCalls = 0

    installApiMock(
      (input, init) => {
        const url = String(input)
        if (url.includes('/workspace')) {
          return jsonResponse(makeWorkspace())
        }
        if (url.includes('/messages') && (!init?.method || init.method === 'GET')) {
          return jsonResponse(makeMessagesResponse([]))
        }
        if (url.includes('/interactions') && init?.method === 'POST') {
          interactionCalls += 1
          if (interactionCalls === 1) {
            return jsonResponse({ detail: 'Upstream model failure' }, 500)
          }
          return jsonResponse(makeInteractionResponse())
        }
        throw new Error(`Unexpected fetch: ${url}`)
      },
      { autoEmptyMessages: false },
    )

    renderApp({
      initialEntries: [`/cases/${SAMPLE_CASE_UUID}/conversation`],
    })
    await screen.findByRole('heading', { name: 'Conversation' })

    await user.type(screen.getByLabelText('Message'), 'Need help with overtime')
    await user.click(screen.getByRole('button', { name: 'Send message' }))

    expect(
      await screen.findByRole('button', { name: 'Retry' }),
    ).toBeInTheDocument()
    expect(screen.getByLabelText('Message')).toHaveValue(
      'Need help with overtime',
    )

    await user.click(screen.getByRole('button', { name: 'Retry' }))
    expect(
      await screen.findByText(
        'Article 10 addresses overtime distribution by seniority.',
      ),
    ).toBeInTheDocument()
    expect(interactionCalls).toBe(2)
  })

  it('ignores late interaction responses after case switch', async () => {
    const user = userEvent.setup()
    let resolveA: ((value: Response) => void) | undefined

    installApiMock(
      (input, init) => {
        const url = String(input)
        if (url.includes(`/cases/${SAMPLE_CASE_UUID}/workspace`)) {
          return jsonResponse(
            makeWorkspace({ title: 'Case Alpha', initial_question: 'Alpha Q' }),
          )
        }
        if (url.includes(`/cases/${OTHER_CASE_UUID}/workspace`)) {
          return jsonResponse(
            makeWorkspace({
              case_uuid: OTHER_CASE_UUID,
              title: 'Case Beta',
              initial_question: 'Beta Q',
            }),
          )
        }
        if (url.includes('/messages') && (!init?.method || init.method === 'GET')) {
          const caseUuid = url.includes(OTHER_CASE_UUID)
            ? OTHER_CASE_UUID
            : SAMPLE_CASE_UUID
          return jsonResponse(makeMessagesResponse([], { case_uuid: caseUuid }))
        }
        if (
          url.includes(`/cases/${SAMPLE_CASE_UUID}/interactions`) &&
          init?.method === 'POST'
        ) {
          return new Promise<Response>((resolve) => {
            resolveA = resolve
          })
        }
        throw new Error(`Unexpected fetch: ${url}`)
      },
      { autoEmptyMessages: false },
    )

    const { router } = renderApp({
      initialEntries: [`/cases/${SAMPLE_CASE_UUID}/conversation`],
    })
    await screen.findByRole('heading', { name: 'Case Alpha' })

    await user.type(screen.getByLabelText('Message'), 'Alpha only question')
    await user.click(screen.getByRole('button', { name: 'Send message' }))
    expect(await screen.findByText('Alpha only question')).toBeInTheDocument()

    await router.navigate(`/cases/${OTHER_CASE_UUID}/conversation`)
    expect(
      await screen.findByRole('heading', { name: 'Case Beta' }),
    ).toBeInTheDocument()

    resolveA!(
      jsonResponse(
        makeInteractionResponse({
          ai_answer: 'Late alpha answer must not appear',
          assistant_message: {
            id: 999,
            role: 'assistant',
            content: 'Late alpha answer must not appear',
            created_at: '2026-07-24T22:00:00Z',
          },
        }),
      ),
    )

    await waitFor(() => {
      expect(
        screen.queryByText('Late alpha answer must not appear'),
      ).not.toBeInTheDocument()
    })
    expect(screen.queryByText('Alpha only question')).not.toBeInTheDocument()
  })

  it('renders retrieval statuses, citations, disclosures, and facts needed', async () => {
    const user = userEvent.setup()
    const citation = makeCitation({ page: undefined })
    const ungrounded = makeCitation({
      document_type: '',
      document_name: 'Speculative note',
      grounded: false,
      grounding_provenance: 'ungrounded',
      quote: 'Not from corpus.',
      page: null,
      article_or_section: '',
    })

    workspaceAndMessages(
      makeMessagesResponse([
        makeCaseMessage({ id: 1, role: 'user', content: 'Ask' }),
        makeCaseMessage({
          id: 2,
          role: 'assistant',
          content: 'Answer with research',
          metadata: {
            citations: [citation, ungrounded],
            disclosures: ['This is guidance, not legal advice.'],
            facts_needed: ['written overtime posting'],
            retrieval_status: 'ok',
          },
        }),
        makeCaseMessage({
          id: 3,
          role: 'assistant',
          content: 'Empty retrieval turn',
          metadata: {
            citations: [],
            disclosures: ['No relevant indexed passage was found.'],
            facts_needed: [],
            retrieval_status: 'empty',
          },
          created_at: '2026-07-20T16:00:00Z',
        }),
        makeCaseMessage({
          id: 4,
          role: 'assistant',
          content: 'Failed retrieval turn',
          metadata: {
            citations: [],
            disclosures: [],
            facts_needed: [],
            retrieval_status: 'failed',
            retrieval_error: true,
          },
          created_at: '2026-07-20T17:00:00Z',
        }),
        makeCaseMessage({
          id: 5,
          role: 'assistant',
          content: 'Skipped retrieval turn',
          metadata: {
            citations: [],
            disclosures: ['Retrieval skipped for this turn.'],
            facts_needed: [],
            retrieval_status: 'skipped',
          },
          created_at: '2026-07-20T18:00:00Z',
        }),
      ]),
    )

    renderApp({
      initialEntries: [`/cases/${SAMPLE_CASE_UUID}/conversation`],
    })

    expect(await screen.findByText('Answer with research')).toBeInTheDocument()
    expect(
      screen.getByText(/Retrieval status: matched authorities/i),
    ).toBeInTheDocument()
    expect(
      screen.getByText(/Retrieval status: empty/i),
    ).toBeInTheDocument()
    expect(
      screen.getByText(/Retrieval status: failed/i),
    ).toBeInTheDocument()
    expect(
      screen.getByText(/Retrieval status: skipped/i),
    ).toBeInTheDocument()
    expect(
      screen.getByText('This is guidance, not legal advice.'),
    ).toBeInTheDocument()
    expect(screen.getByText('written overtime posting')).toBeInTheDocument()

    const chip = screen.getByRole('button', {
      name: /CBA · Article 10/i,
    })
    await user.click(chip)

    const research = screen.getByRole('complementary', { name: 'Research' })
    expect(within(research).getByText('Local 300 Agreement')).toBeInTheDocument()
    expect(within(research).queryByText(/^Page$/i)).not.toBeInTheDocument()
    expect(within(research).getByText(/Overtime shall be offered/i)).toBeInTheDocument()

    await user.click(
      screen.getByRole('button', { name: /Speculative note \(ungrounded\)/i }),
    )
    expect(
      within(research).getByText(/not grounded in a retrieved passage/i),
    ).toBeInTheDocument()
    expect(within(research).queryByText('null')).not.toBeInTheDocument()
    expect(within(research).queryByText('undefined')).not.toBeInTheDocument()

    await user.click(
      screen.getAllByRole('button', { name: 'Open Known Facts editor' })[0]!,
    )
    expect(document.activeElement).not.toBe(document.body)
    expect(
      document.getElementById('known-facts-editor')?.contains(document.activeElement),
    ).toBe(true)
  })

  it('does not invalidate Case Memory workspace when memory unchanged', async () => {
    const user = userEvent.setup()
    installApiMock(
      (input, init) => {
        const url = String(input)
        if (url.includes('/workspace')) {
          return jsonResponse(makeWorkspace())
        }
        if (url.includes('/messages') && (!init?.method || init.method === 'GET')) {
          return jsonResponse(makeMessagesResponse([]))
        }
        if (url.includes('/interactions') && init?.method === 'POST') {
          return jsonResponse(
            makeInteractionResponse({
              case_memory_update_status: 'not_applicable',
            }),
          )
        }
        throw new Error(`Unexpected fetch: ${url}`)
      },
      { autoEmptyMessages: false },
    )

    const { queryClient } = renderApp({
      initialEntries: [`/cases/${SAMPLE_CASE_UUID}/conversation`],
    })
    await screen.findByRole('heading', { name: 'Conversation' })
    const invalidateSpy = vi.spyOn(queryClient, 'invalidateQueries')

    await user.type(screen.getByLabelText('Message'), 'Ordinary note')
    await user.click(screen.getByRole('button', { name: 'Send message' }))
    await screen.findByText(
      'Article 10 addresses overtime distribution by seniority.',
    )

    expect(invalidateSpy).not.toHaveBeenCalledWith(
      expect.objectContaining({
        queryKey: workspaceKeys.detail(SAMPLE_CASE_UUID),
      }),
    )
  })

  it('direct navigation restores conversation without auto-sending', async () => {
    const fetchMock = workspaceAndMessages(
      makeMessagesResponse([
        makeCaseMessage({ content: 'Persisted steward message' }),
        makeCaseMessage({
          id: 2,
          role: 'assistant',
          content: 'Persisted assistant message',
          metadata: {},
        }),
      ]),
    )

    renderApp({
      initialEntries: [`/cases/${SAMPLE_CASE_UUID}/conversation`],
    })

    expect(
      await screen.findByText('Persisted steward message'),
    ).toBeInTheDocument()
    expect(screen.getByText('Persisted assistant message')).toBeInTheDocument()

    const interactionPosts = fetchMock.mock.calls.filter(
      ([request, init]) =>
        String(request).includes('/interactions') && init?.method === 'POST',
    )
    expect(interactionPosts).toHaveLength(0)
  })

  it('does not call analysis, grievance, artifact, or sources endpoints', async () => {
    const user = userEvent.setup()
    const fetchMock = installApiMock(
      (input, init) => {
        const url = String(input)
        if (url.includes('/workspace')) {
          return jsonResponse(makeWorkspace())
        }
        if (url.includes('/messages') && (!init?.method || init.method === 'GET')) {
          return jsonResponse(makeMessagesResponse([]))
        }
        if (url.includes('/interactions') && init?.method === 'POST') {
          return jsonResponse(makeInteractionResponse())
        }
        throw new Error(`Unexpected fetch: ${url}`)
      },
      { autoEmptyMessages: false },
    )

    renderApp({
      initialEntries: [`/cases/${SAMPLE_CASE_UUID}/conversation`],
    })
    await screen.findByRole('heading', { name: 'Conversation' })
    await user.type(screen.getByLabelText('Message'), 'Safe chat only')
    await user.click(screen.getByRole('button', { name: 'Send message' }))
    await screen.findByText(
      'Article 10 addresses overtime distribution by seniority.',
    )

    for (const [request] of fetchMock.mock.calls) {
      const url = String(request)
      expect(url).not.toMatch(/\/reports\//)
      expect(url).not.toMatch(/\/grievances\//)
      expect(url).not.toMatch(/\/artifacts/)
      expect(url).not.toMatch(/\/sources\//)
      expect(url).not.toMatch(/react-server/)
    }
  })

  it('Enter submits and Shift+Enter keeps a newline', async () => {
    const user = userEvent.setup()
    const bodies: unknown[] = []
    installApiMock(
      (input, init) => {
        const url = String(input)
        if (url.includes('/workspace')) {
          return jsonResponse(makeWorkspace())
        }
        if (url.includes('/messages') && (!init?.method || init.method === 'GET')) {
          return jsonResponse(makeMessagesResponse([]))
        }
        if (url.includes('/interactions') && init?.method === 'POST') {
          bodies.push(JSON.parse(String(init.body)))
          return jsonResponse(makeInteractionResponse())
        }
        throw new Error(`Unexpected fetch: ${url}`)
      },
      { autoEmptyMessages: false },
    )

    renderApp({
      initialEntries: [`/cases/${SAMPLE_CASE_UUID}/conversation`],
    })
    await screen.findByRole('heading', { name: 'Conversation' })

    const composer = screen.getByLabelText('Message')
    await user.type(composer, 'Line one')
    await user.keyboard('{Shift>}{Enter}{/Shift}')
    await user.type(composer, 'Line two')
    expect(composer).toHaveValue('Line one\nLine two')

    await user.keyboard('{Enter}')
    await waitFor(() => {
      expect(bodies).toHaveLength(1)
    })
    expect(bodies[0]).toEqual({
      message: 'Line one\nLine two',
      source: 'manual_ui',
    })
  })
})
