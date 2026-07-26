import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { act, renderHook, waitFor } from '@testing-library/react'
import type { ReactNode } from 'react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import {
  analysisKeys,
  artifactKeys,
  grievanceKeys,
  messageKeys,
  workflowKeys,
  workspaceKeys,
} from '../features/cases/savedCaseActions'
import { useSaveAnalysisMutation } from '../features/cases/useSaveAnalysisMutation'
import { useSaveGrievanceMutation } from '../features/cases/useSaveGrievanceMutation'
import { researchKeys } from '../features/research/researchKeys'
import { installApiMock, jsonResponse } from './savedCasesFixtures'

/**
 * W6 remediation A: Save and Save-and-Print always create/update a
 * CaseSavedArtifact, append a timeline event, and attempt a workflow
 * transition. These tests prove the mutations refresh exactly those
 * case-scoped resources — and nothing belonging to another case or an
 * unrelated feature (Conversation, Sources Research).
 */

const CASE_X_UUID = '44444444-4444-4444-8444-444444444444'
const CASE_Y_UUID = '55555555-5555-4555-8555-555555555555'

function createIsolatedQueryClient(): QueryClient {
  return new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false },
    },
  })
}

function wrapperFor(queryClient: QueryClient) {
  return function Wrapper({ children }: { children: ReactNode }) {
    return (
      <QueryClientProvider client={queryClient}>
        {children}
      </QueryClientProvider>
    )
  }
}

type KeyFamilies = Record<string, readonly unknown[]>

function isInvalidated(queryClient: QueryClient, queryKey: readonly unknown[]): boolean {
  return (
    queryClient.getQueryCache().find({ queryKey, exact: true })?.state
      .isInvalidated ?? false
  )
}

/** Every durable resource a Save/Save-and-Print must refresh, for one case. */
function caseScopedFamilies(caseUuid: string): KeyFamilies {
  return {
    artifactList: artifactKeys.list(caseUuid),
    artifactDetail: artifactKeys.detail(caseUuid, 'artifact-1'),
    artifactHistory: artifactKeys.history(caseUuid),
    artifactTimeline: artifactKeys.timeline(caseUuid),
    workflow: workflowKeys.detail(caseUuid),
    workspace: workspaceKeys.detail(caseUuid),
  }
}

/** Feature areas the Save mutations must never touch. */
function unrelatedFamilies(caseUuid: string): KeyFamilies {
  return {
    conversationMessages: messageKeys.list(caseUuid, {
      limit: 20,
      offset: 0,
      order: 'asc',
    }),
    sourcesResearchMeta: researchKeys.meta(),
  }
}

function seed(queryClient: QueryClient, families: KeyFamilies, tag: string) {
  for (const key of Object.values(families)) {
    queryClient.setQueryData(key as unknown[], { seeded: tag })
  }
}

function invalidationSnapshot(
  queryClient: QueryClient,
  families: KeyFamilies,
): Record<string, boolean> {
  const snapshot: Record<string, boolean> = {}
  for (const [name, key] of Object.entries(families)) {
    snapshot[name] = isInvalidated(queryClient, key)
  }
  return snapshot
}

function allExpected(families: KeyFamilies, value: boolean): Record<string, boolean> {
  return Object.fromEntries(Object.keys(families).map((name) => [name, value]))
}

describe('W6 remediation A: Save mutations invalidate case-scoped caches only', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('useSaveAnalysisMutation refreshes artifact/history/timeline/workflow for the saved case only', async () => {
    installApiMock((input, init) => {
      const url = typeof input === 'string' ? input : input.toString()
      const method = (init?.method ?? 'GET').toUpperCase()
      if (
        method === 'POST' &&
        url.includes(`/cases/${CASE_X_UUID}/reports/save-and-print`)
      ) {
        return jsonResponse({
          case_uuid: CASE_X_UUID,
          status: 'saved',
          message: 'Saved',
          artifact: {
            artifact_uuid: 'artifact-analysis-1',
            case_uuid: CASE_X_UUID,
            artifact_type: 'analysis_report',
            title: 'Analysis v1',
            version_number: 1,
            version_label: 'v1',
            saved_at: '2026-07-25T00:00:00Z',
            source_report_version_number: 3,
          },
        })
      }
      return jsonResponse({ detail: `Unhandled mock: ${method} ${url}` }, 500)
    })

    const queryClient = createIsolatedQueryClient()
    const caseXFamilies = caseScopedFamilies(CASE_X_UUID)
    const caseYFamilies = caseScopedFamilies(CASE_Y_UUID)
    const otherFamilies = unrelatedFamilies(CASE_X_UUID)
    seed(queryClient, caseXFamilies, CASE_X_UUID)
    seed(queryClient, caseYFamilies, CASE_Y_UUID)
    seed(queryClient, otherFamilies, CASE_X_UUID)
    queryClient.setQueryData(analysisKeys.list(CASE_X_UUID), {
      seeded: CASE_X_UUID,
    })

    const { result } = renderHook(() => useSaveAnalysisMutation(), {
      wrapper: wrapperFor(queryClient),
    })

    act(() => {
      result.current.mutate({
        caseUuid: CASE_X_UUID,
        body: { prepare_pdf: false },
      })
    })

    await waitFor(() => expect(result.current.isSuccess).toBe(true))

    expect(invalidationSnapshot(queryClient, caseXFamilies)).toEqual(
      allExpected(caseXFamilies, true),
    )
    expect(invalidationSnapshot(queryClient, caseYFamilies)).toEqual(
      allExpected(caseYFamilies, false),
    )
    expect(invalidationSnapshot(queryClient, otherFamilies)).toEqual(
      allExpected(otherFamilies, false),
    )
  })

  it('useSaveGrievanceMutation refreshes artifact/history/timeline/workflow for the saved case only', async () => {
    installApiMock((input, init) => {
      const url = typeof input === 'string' ? input : input.toString()
      const method = (init?.method ?? 'GET').toUpperCase()
      if (
        method === 'POST' &&
        url.includes(`/cases/${CASE_X_UUID}/grievances/save-and-print`)
      ) {
        return jsonResponse({
          case_uuid: CASE_X_UUID,
          status: 'saved',
          message: 'Saved',
          artifact: {
            artifact_uuid: 'artifact-grievance-1',
            case_uuid: CASE_X_UUID,
            artifact_type: 'grievance_form',
            title: 'Grievance v1',
            version_number: 1,
            version_label: 'v1',
            saved_at: '2026-07-25T00:00:00Z',
          },
        })
      }
      return jsonResponse({ detail: `Unhandled mock: ${method} ${url}` }, 500)
    })

    const queryClient = createIsolatedQueryClient()
    const caseXFamilies = caseScopedFamilies(CASE_X_UUID)
    const caseYFamilies = caseScopedFamilies(CASE_Y_UUID)
    const otherFamilies = unrelatedFamilies(CASE_X_UUID)
    seed(queryClient, caseXFamilies, CASE_X_UUID)
    seed(queryClient, caseYFamilies, CASE_Y_UUID)
    seed(queryClient, otherFamilies, CASE_X_UUID)
    queryClient.setQueryData(grievanceKeys.list(CASE_X_UUID), {
      seeded: CASE_X_UUID,
    })

    const { result } = renderHook(() => useSaveGrievanceMutation(), {
      wrapper: wrapperFor(queryClient),
    })

    act(() => {
      result.current.mutate({
        caseUuid: CASE_X_UUID,
        body: {
          template_id: 'official_grievance_worksheet_step_1',
          field_values: {},
        },
      })
    })

    await waitFor(() => expect(result.current.isSuccess).toBe(true))

    expect(invalidationSnapshot(queryClient, caseXFamilies)).toEqual(
      allExpected(caseXFamilies, true),
    )
    expect(invalidationSnapshot(queryClient, caseYFamilies)).toEqual(
      allExpected(caseYFamilies, false),
    )
    expect(invalidationSnapshot(queryClient, otherFamilies)).toEqual(
      allExpected(otherFamilies, false),
    )
  })
})
