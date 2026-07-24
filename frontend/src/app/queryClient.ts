import { QueryClient } from '@tanstack/react-query'
import { ApiError } from '../api/client'

function shouldRetryQuery(failureCount: number, error: unknown): boolean {
  if (failureCount >= 2) {
    return false
  }
  if (error instanceof ApiError) {
    if (error.status === 0) {
      return true
    }
    if (error.status >= 500) {
      return true
    }
    return false
  }
  return failureCount < 1
}

export function createQueryClient(): QueryClient {
  return new QueryClient({
    defaultOptions: {
      queries: {
        retry: shouldRetryQuery,
        refetchOnWindowFocus: true,
        staleTime: 30_000,
      },
      mutations: {
        retry: false,
      },
    },
  })
}
