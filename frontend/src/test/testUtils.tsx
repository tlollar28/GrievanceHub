import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render } from '@testing-library/react'
import type { ReactElement, ReactNode } from 'react'
import { createMemoryRouter, RouterProvider } from 'react-router-dom'
import { appRoutes } from '../app/routes'

export function createTestQueryClient(): QueryClient {
  return new QueryClient({
    defaultOptions: {
      queries: {
        retry: false,
        refetchOnWindowFocus: false,
      },
      mutations: {
        retry: false,
      },
    },
  })
}

type RenderOptions = {
  initialEntries?: string[]
  queryClient?: QueryClient
}

function Providers({
  children,
  queryClient,
}: {
  children: ReactNode
  queryClient: QueryClient
}) {
  return (
    <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  )
}

export function renderApp(options: RenderOptions = {}) {
  const queryClient = options.queryClient ?? createTestQueryClient()
  const router = createMemoryRouter(appRoutes, {
    initialEntries: options.initialEntries ?? ['/dashboard'],
  })

  const view = render(<RouterProvider router={router} />, {
    wrapper: ({ children }) => (
      <Providers queryClient={queryClient}>{children}</Providers>
    ),
  })

  return {
    queryClient,
    router,
    ...view,
    unmount: () => {
      view.unmount()
      queryClient.clear()
    },
  }
}

export function renderWithProviders(
  ui: ReactElement,
  options: { queryClient?: QueryClient } = {},
) {
  const queryClient = options.queryClient ?? createTestQueryClient()

  return {
    queryClient,
    ...render(ui, {
      wrapper: ({ children }) => (
        <Providers queryClient={queryClient}>{children}</Providers>
      ),
    }),
  }
}
