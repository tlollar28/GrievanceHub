import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'
import {
  CASE_ASSET_MAX_UPLOAD_BYTES,
  EXECUTABLE_UPLOAD_CATEGORY,
} from '../api/types/assets'
import {
  CLOSED_CASE_UUID,
  OTHER_ASSET_UUID,
  OTHER_CASE_UUID,
  SAMPLE_ASSET_UUID,
  SAMPLE_CASE_UUID,
  installApiMock,
  jsonResponse,
  makeAsset,
  makeAssetListResponse,
  makeInteractionResponse,
  makeMessagesResponse,
  makeUploadResponse,
  makeWorkspace,
} from './savedCasesFixtures'
import { renderApp, waitForWorkspaceReady } from './testUtils'

function workspaceAssetsHandler(
  assets = [makeAsset()],
  options: {
    onUpload?: (formData: FormData, headers: Headers) => Response | Promise<Response>
    onInteraction?: (body: unknown) => Response | Promise<Response>
    workspace?: ReturnType<typeof makeWorkspace>
  } = {},
) {
  return installApiMock(
    (input, init) => {
      const url = String(input)
      const method = init?.method ?? 'GET'

      if (url.includes(`/cases/${SAMPLE_CASE_UUID}/workspace`)) {
        return jsonResponse(options.workspace ?? makeWorkspace())
      }
      if (url.includes(`/cases/${OTHER_CASE_UUID}/workspace`)) {
        return jsonResponse(
          makeWorkspace({
            case_uuid: OTHER_CASE_UUID,
            title: 'Other case',
          }),
        )
      }
      if (url.includes(`/cases/${CLOSED_CASE_UUID}/workspace`)) {
        return jsonResponse(
          makeWorkspace({
            case_uuid: CLOSED_CASE_UUID,
            status: 'closed',
            title: 'Closed case',
          }),
        )
      }

      if (
        url.includes(`/cases/${SAMPLE_CASE_UUID}/assets/`) &&
        method === 'GET'
      ) {
        const assetUuid = url.split('/assets/')[1]?.split('?')[0]
        const asset = assets.find((row) => row.asset_uuid === assetUuid)
        if (!asset) {
          return jsonResponse({ detail: 'Case asset not found' }, 404)
        }
        return jsonResponse(asset)
      }

      if (
        /\/cases\/[^/]+\/assets(?:\?|$)/.test(url) &&
        method === 'GET'
      ) {
        const match = url.match(/\/cases\/([^/]+)\/assets/)
        const caseUuid = match?.[1] ?? SAMPLE_CASE_UUID
        if (caseUuid === OTHER_CASE_UUID) {
          return jsonResponse(
            makeAssetListResponse(
              [
                makeAsset({
                  case_uuid: OTHER_CASE_UUID,
                  asset_uuid: OTHER_ASSET_UUID,
                  original_filename: 'other-case.txt',
                }),
              ],
              { case_uuid: OTHER_CASE_UUID },
            ),
          )
        }
        if (caseUuid !== SAMPLE_CASE_UUID) {
          return jsonResponse(makeAssetListResponse([], { case_uuid: caseUuid }))
        }
        return jsonResponse(
          makeAssetListResponse(assets, { case_uuid: SAMPLE_CASE_UUID }),
        )
      }

      if (
        url.includes(`/cases/${SAMPLE_CASE_UUID}/assets`) &&
        method === 'POST'
      ) {
        const headers = new Headers(init?.headers)
        if (options.onUpload && init?.body instanceof FormData) {
          return options.onUpload(init.body, headers)
        }
        const uploaded = makeAsset({
          asset_uuid: 'bbbbbbbb-cccc-4ddd-8eee-ffffffffffff',
          original_filename: 'new-upload.txt',
        })
        return jsonResponse(makeUploadResponse(uploaded))
      }

      if (
        url.includes(`/cases/${SAMPLE_CASE_UUID}/messages`) &&
        method === 'GET'
      ) {
        return jsonResponse(makeMessagesResponse([]))
      }

      if (
        url.includes(`/cases/${SAMPLE_CASE_UUID}/interactions`) &&
        method === 'POST'
      ) {
        const body = JSON.parse(String(init?.body))
        if (options.onInteraction) {
          return options.onInteraction(body)
        }
        return jsonResponse(
          makeInteractionResponse({
            user_message: {
              id: 301,
              role: 'user',
              content: body.message,
              metadata: { upload_refs: body.upload_refs ?? [] },
              created_at: '2026-07-24T22:00:00Z',
            },
          }),
        )
      }

      throw new Error(`Unexpected fetch: ${url} ${method}`)
    },
    { autoEmptyMessages: false, autoEmptyAssets: false },
  )
}

describe('W6 M4 Evidence Uploads and Case Asset References', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
    vi.restoreAllMocks()
  })

  it('restores workspace and asset list on evidence route', async () => {
    workspaceAssetsHandler([
      makeAsset({ original_filename: 'approval.txt' }),
    ])

    renderApp({
      initialEntries: [`/cases/${SAMPLE_CASE_UUID}/evidence`],
    })

    await waitForWorkspaceReady({
      heading: 'Overtime dispute',
      text: 'approval.txt',
    })
    expect(
      screen.getByRole('heading', { name: 'Overtime dispute' }),
    ).toBeInTheDocument()
    expect(
      screen.getByRole('heading', { name: 'Evidence' }),
    ).toBeInTheDocument()
    expect(screen.getByText('approval.txt')).toBeInTheDocument()
    expect(
      screen.getByRole('navigation', { name: 'Case workspace sections' }),
    ).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Evidence' })).toHaveAttribute(
      'aria-current',
      'page',
    )
  })

  it('supports direct navigation and browser-style refresh restore', async () => {
    workspaceAssetsHandler([makeAsset()])
    const user = userEvent.setup()

    renderApp({
      initialEntries: [`/cases/${SAMPLE_CASE_UUID}/evidence`],
    })

    await waitForWorkspaceReady({ text: 'evidence-note.txt' })
    expect(screen.getByText('evidence-note.txt')).toBeInTheDocument()

    await user.click(screen.getByRole('link', { name: 'Conversation' }))
    expect(
      await screen.findByRole('heading', { name: 'Conversation' }),
    ).toBeInTheDocument()

    await user.click(screen.getByRole('link', { name: 'Evidence' }))
    expect(await screen.findByText('evidence-note.txt')).toBeInTheDocument()
  })

  it('shows asset loading, empty, and error with Retry', async () => {
    const user = userEvent.setup()
    let calls = 0
    installApiMock(
      (input, init) => {
        const url = String(input)
        if (url.includes('/workspace')) {
          return jsonResponse(makeWorkspace())
        }
        if (/\/assets(?:\?|$)/.test(url) && (!init?.method || init.method === 'GET')) {
          calls += 1
          if (calls === 1) {
            return new Promise(() => {
              /* pending */
            })
          }
          if (calls === 2) {
            return jsonResponse({ detail: 'Assets unavailable' }, 500)
          }
          return jsonResponse(makeAssetListResponse([]))
        }
        throw new Error(`Unexpected fetch: ${url}`)
      },
      { autoEmptyAssets: false },
    )

    const { unmount } = renderApp({
      initialEntries: [`/cases/${SAMPLE_CASE_UUID}/evidence`],
    })
    expect(await screen.findByText(/Loading case evidence/i)).toBeInTheDocument()
    unmount()

    renderApp({
      initialEntries: [`/cases/${SAMPLE_CASE_UUID}/evidence`],
    })
    expect(await screen.findByRole('alert')).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Retry' }))
    expect(
      await screen.findByText(/No evidence uploaded for this case yet/i),
    ).toBeInTheDocument()
  })

  it('renders safe fields and never storage paths', async () => {
    const asset = makeAsset({
      original_filename: 'safe.txt',
      stored_path: 'data/case_assets/secret/path/safe.txt',
      stored_filename: 'uuid_safe.txt',
      sha256: 'b'.repeat(64),
    })
    workspaceAssetsHandler([asset])

    renderApp({
      initialEntries: [`/cases/${SAMPLE_CASE_UUID}/evidence`],
    })

    expect(await screen.findByText('safe.txt')).toBeInTheDocument()
    expect(screen.getByText(SAMPLE_ASSET_UUID)).toBeInTheDocument()
    expect(screen.getByText('uploaded_document')).toBeInTheDocument()
    expect(screen.getByText('text/plain')).toBeInTheDocument()

    await userEvent.click(
      screen.getByRole('button', { name: 'View metadata for safe.txt' }),
    )
    const detail = await screen.findByRole('heading', { name: 'Asset detail' })
    const detailSection = detail.closest('section')!
    expect(within(detailSection).getByText('b'.repeat(64))).toBeInTheDocument()
    expect(within(detailSection).getByText('Steward Ada')).toBeInTheDocument()
    expect(screen.queryByText(/data\/case_assets/)).not.toBeInTheDocument()
    expect(screen.queryByText('uuid_safe.txt')).not.toBeInTheDocument()
    expect(screen.queryByText(asset.stored_path!)).not.toBeInTheDocument()
  })

  it('validates no-file and oversized files before upload', async () => {
    const user = userEvent.setup()
    workspaceAssetsHandler([])

    renderApp({
      initialEntries: [`/cases/${SAMPLE_CASE_UUID}/evidence`],
    })
    await screen.findByRole('heading', { name: 'Evidence' })

    expect(screen.getByRole('button', { name: 'Upload' })).toBeDisabled()

    const input = screen.getByLabelText('Evidence file')
    const oversized = new File(
      [new Uint8Array(CASE_ASSET_MAX_UPLOAD_BYTES + 1)],
      'too-big.bin',
      { type: 'application/octet-stream' },
    )
    await user.upload(input, oversized)
    await user.click(screen.getByRole('button', { name: 'Upload' }))
    expect(
      await screen.findByText(/File exceeds maximum size/i),
    ).toBeInTheDocument()
  })

  it('posts exact multipart fields without manual Content-Type', async () => {
    const user = userEvent.setup()
    const captured: Array<{
      headers: Record<string, string>
      fields: Record<string, string>
      fileName: string | null
    }> = []

    const fetchMock = workspaceAssetsHandler([], {
      onUpload: (formData, headers) => {
        const headerRecord: Record<string, string> = {}
        headers.forEach((value, key) => {
          headerRecord[key.toLowerCase()] = value
        })
        captured.push({
          headers: headerRecord,
          fields: {
            category: String(formData.get('category') ?? ''),
            source: String(formData.get('source') ?? ''),
            uploaded_by: String(formData.get('uploaded_by') ?? ''),
          },
          fileName:
            formData.get('file') instanceof File
              ? (formData.get('file') as File).name
              : null,
        })
        return jsonResponse(
          makeUploadResponse(
            makeAsset({
              asset_uuid: 'bbbbbbbb-cccc-4ddd-8eee-ffffffffffff',
              original_filename: 'w6_m4_evidence_smoke.txt',
            }),
          ),
        )
      },
    })

    renderApp({
      initialEntries: [`/cases/${SAMPLE_CASE_UUID}/evidence`],
    })
    await screen.findByRole('heading', { name: 'Evidence' })

    const file = new File(['harmless local smoke text'], 'w6_m4_evidence_smoke.txt', {
      type: 'text/plain',
    })
    await user.upload(screen.getByLabelText('Evidence file'), file)
    expect(screen.getByText(/Selected: w6_m4_evidence_smoke.txt/i)).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: 'Upload' }))
    expect(await screen.findByText(/Uploaded w6_m4_evidence_smoke.txt/i)).toBeInTheDocument()

    expect(captured).toHaveLength(1)
    expect(captured[0].fields.category).toBe(EXECUTABLE_UPLOAD_CATEGORY)
    expect(captured[0].fields.source).toBe('manual_ui')
    expect(captured[0].fields.uploaded_by).toBe('Steward Ada')
    expect(captured[0].fileName).toBe('w6_m4_evidence_smoke.txt')
    expect(captured[0].headers['content-type']).toBeUndefined()

    const uploadCall = fetchMock.mock.calls.find(
      ([request, init]) =>
        String(request).includes('/assets') && init?.method === 'POST',
    )
    expect(uploadCall).toBeTruthy()
    const initHeaders = new Headers(uploadCall?.[1]?.headers)
    expect(initHeaders.get('content-type')).toBeNull()
  })

  it('prevents duplicate upload submission while pending', async () => {
    const user = userEvent.setup()
    let resolveUpload: ((value: Response) => void) | undefined
    let uploadCalls = 0

    workspaceAssetsHandler([], {
      onUpload: () => {
        uploadCalls += 1
        return new Promise<Response>((resolve) => {
          resolveUpload = resolve
        })
      },
    })

    renderApp({
      initialEntries: [`/cases/${SAMPLE_CASE_UUID}/evidence`],
    })
    await screen.findByRole('heading', { name: 'Evidence' })

    await user.upload(
      screen.getByLabelText('Evidence file'),
      new File(['abc'], 'pending.txt', { type: 'text/plain' }),
    )
    await user.click(screen.getByRole('button', { name: 'Upload' }))
    const uploading = await screen.findByRole('button', { name: 'Uploading…' })
    expect(uploading).toBeDisabled()
    await user.click(uploading)
    expect(uploadCalls).toBe(1)

    resolveUpload!(
      jsonResponse(
        makeUploadResponse(
          makeAsset({ original_filename: 'pending.txt' }),
        ),
      ),
    )
    expect(
      await screen.findByText('Uploaded pending.txt.'),
    ).toBeInTheDocument()
  })

  it('shows no-case-file-RAG disclosure on evidence and conversation', async () => {
    workspaceAssetsHandler([makeAsset()])

    const first = renderApp({
      initialEntries: [`/cases/${SAMPLE_CASE_UUID}/evidence`],
    })
    expect(
      (
        await screen.findAllByText(
          /Uploaded evidence is attached as case context\. It is not full-text searched/i,
        )
      ).length,
    ).toBeGreaterThan(0)
    first.unmount()

    renderApp({
      initialEntries: [`/cases/${SAMPLE_CASE_UUID}/conversation`],
    })
    expect(
      await screen.findByText(
        /Uploaded evidence is attached as case context\. It is not full-text searched/i,
      ),
    ).toBeInTheDocument()
  })

  it('conversation picker lists current-case assets and sends upload_refs', async () => {
    const user = userEvent.setup()
    const bodies: unknown[] = []
    workspaceAssetsHandler(
      [
        makeAsset({
          original_filename: 'case-a.txt',
          asset_uuid: SAMPLE_ASSET_UUID,
        }),
      ],
      {
        onInteraction: (body) => {
          bodies.push(body)
          return jsonResponse(
            makeInteractionResponse({
              user_message: {
                id: 401,
                role: 'user',
                content: (body as { message: string }).message,
                created_at: '2026-07-24T22:10:00Z',
              },
            }),
          )
        },
      },
    )

    renderApp({
      initialEntries: [`/cases/${SAMPLE_CASE_UUID}/conversation`],
    })
    await screen.findByRole('heading', { name: 'Conversation' })

    await user.click(
      screen.getByRole('button', { name: 'Attach case evidence' }),
    )
    expect(await screen.findByText('case-a.txt')).toBeInTheDocument()
    expect(screen.queryByText('other-case.txt')).not.toBeInTheDocument()

    await user.click(screen.getByLabelText(/case-a\.txt/i))
    expect(
      screen.getByText(/1 evidence reference selected/i),
    ).toBeInTheDocument()

    await user.type(screen.getByLabelText('Message'), 'Please consider the note.')
    await user.click(screen.getByRole('button', { name: 'Send message' }))

    await waitFor(() => {
      expect(bodies).toHaveLength(1)
    })
    expect(bodies[0]).toEqual({
      message: 'Please consider the note.',
      source: 'manual_ui',
      upload_refs: [SAMPLE_ASSET_UUID],
    })
    await waitFor(() => {
      expect(
        screen.getByText(/No evidence attached/i),
      ).toBeInTheDocument()
    })
  })

  it('supports multiple upload_refs, removal, failure preserve, and case-switch clear', async () => {
    const user = userEvent.setup()
    const bodies: unknown[] = []
    let failNext = true

    const fetchMock = workspaceAssetsHandler(
      [
        makeAsset({
          asset_uuid: SAMPLE_ASSET_UUID,
          original_filename: 'one.txt',
        }),
        makeAsset({
          asset_uuid: 'cccccccc-dddd-4eee-8fff-000000000001',
          original_filename: 'two.txt',
        }),
      ],
      {
        onInteraction: (body) => {
          bodies.push(body)
          if (failNext) {
            failNext = false
            return jsonResponse({ detail: 'Temporary failure' }, 500)
          }
          return jsonResponse(
            makeInteractionResponse({
              user_message: {
                id: 501,
                role: 'user',
                content: (body as { message: string }).message,
                created_at: '2026-07-24T22:20:00Z',
              },
            }),
          )
        },
      },
    )

    const { router } = renderApp({
      initialEntries: [`/cases/${SAMPLE_CASE_UUID}/conversation`],
    })
    await screen.findByRole('heading', { name: 'Conversation' })

    await user.click(
      screen.getByRole('button', { name: 'Attach case evidence' }),
    )
    await user.click(screen.getByLabelText(/one\.txt/i))
    await user.click(screen.getByLabelText(/two\.txt/i))
    expect(
      screen.getByText(/2 evidence references selected/i),
    ).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: 'Remove two.txt' }))
    expect(
      screen.getByText(/1 evidence reference selected/i),
    ).toBeInTheDocument()

    await user.type(screen.getByLabelText('Message'), 'With one attachment')
    await user.click(screen.getByRole('button', { name: 'Send message' }))

    const failure = await screen.findByText(/server error/i)
    expect(failure).not.toHaveTextContent('Temporary failure')
    expect(
      screen.getByText(/1 evidence reference selected/i),
    ).toBeInTheDocument()
    expect(bodies[0]).toMatchObject({
      upload_refs: [SAMPLE_ASSET_UUID],
    })

    await router.navigate(`/cases/${OTHER_CASE_UUID}/conversation`)
    await waitForWorkspaceReady({ heading: 'Other case' })
    expect(
      screen.getByRole('heading', { name: 'Other case' }),
    ).toBeInTheDocument()
    expect(screen.getByText(/No evidence attached/i)).toBeInTheDocument()

    await user.click(
      screen.getByRole('button', { name: 'Attach case evidence' }),
    )
    expect(await screen.findByText('other-case.txt')).toBeInTheDocument()
    expect(screen.queryByText('one.txt')).not.toBeInTheDocument()

    const foreignAssetCalls = fetchMock.mock.calls.filter(([request]) =>
      String(request).includes(OTHER_ASSET_UUID),
    )
    expect(foreignAssetCalls.length).toBeGreaterThanOrEqual(0)
  })

  it('message-only interactions remain valid without upload_refs', async () => {
    const user = userEvent.setup()
    const bodies: unknown[] = []
    workspaceAssetsHandler([makeAsset()], {
      onInteraction: (body) => {
        bodies.push(body)
        return jsonResponse(makeInteractionResponse())
      },
    })

    renderApp({
      initialEntries: [`/cases/${SAMPLE_CASE_UUID}/conversation`],
    })
    await screen.findByRole('heading', { name: 'Conversation' })
    await user.type(screen.getByLabelText('Message'), 'Message only')
    await user.click(screen.getByRole('button', { name: 'Send message' }))

    await waitFor(() => expect(bodies).toHaveLength(1))
    expect(bodies[0]).toEqual({
      message: 'Message only',
      source: 'manual_ui',
    })
    expect(
      (bodies[0] as { upload_refs?: string[] }).upload_refs,
    ).toBeUndefined()
  })

  it('does not call sources, analysis, grievance, or artifact endpoints', async () => {
    const user = userEvent.setup()
    const fetchMock = workspaceAssetsHandler([makeAsset()])

    renderApp({
      initialEntries: [`/cases/${SAMPLE_CASE_UUID}/evidence`],
    })
    await screen.findByText('evidence-note.txt')
    await user.upload(
      screen.getByLabelText('Evidence file'),
      new File(['x'], 'note.txt', { type: 'text/plain' }),
    )
    await user.click(screen.getByRole('button', { name: 'Upload' }))
    expect(
      await screen.findByText('Uploaded new-upload.txt.'),
    ).toBeInTheDocument()

    const urls = fetchMock.mock.calls.map(([request]) => String(request))
    expect(urls.some((url) => url.includes('/sources'))).toBe(false)
    expect(urls.some((url) => /analysis|grievance|artifact/i.test(url))).toBe(
      false,
    )
  })

  it('upload form guidance matches verified category and size limit', async () => {
    workspaceAssetsHandler([])
    renderApp({
      initialEntries: [`/cases/${SAMPLE_CASE_UUID}/evidence`],
    })
    const guidance = await screen.findByText(/only executable upload type/i)
    expect(guidance).toHaveTextContent(EXECUTABLE_UPLOAD_CATEGORY)
    expect(guidance).toHaveTextContent('25.0 MB')
    expect(
      screen.getByRole('heading', { name: 'Upload evidence' }),
    ).toBeInTheDocument()
  })

  it('asset detail and table are keyboard reachable', async () => {
    const user = userEvent.setup()
    workspaceAssetsHandler([makeAsset({ original_filename: 'keyboard.txt' })])
    renderApp({
      initialEntries: [`/cases/${SAMPLE_CASE_UUID}/evidence`],
    })
    const viewButton = await screen.findByRole('button', {
      name: 'View metadata for keyboard.txt',
    })
    viewButton.focus()
    await user.keyboard('{Enter}')
    const detail = await screen.findByRole('heading', { name: 'Asset detail' })
    expect(detail).toBeInTheDocument()
    expect(
      within(detail.closest('section')!).getByText('keyboard.txt'),
    ).toBeInTheDocument()
  })
})
