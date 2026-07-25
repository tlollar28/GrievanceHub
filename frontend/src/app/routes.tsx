import { Navigate, type RouteObject } from 'react-router-dom'
import { AppShell } from '../components/AppShell'
import { RouteErrorBoundary } from '../components/RouteErrorBoundary'
import { CaseWorkspacePage } from '../routes/CaseWorkspacePage'
import { CasesPage } from '../routes/CasesPage'
import { DashboardPage } from '../routes/DashboardPage'
import { HelpPage } from '../routes/HelpPage'
import { NewCasePage } from '../routes/NewCasePage'
import { NotFoundPage } from '../routes/NotFoundPage'

export const appRoutes: RouteObject[] = [
  {
    path: '/',
    element: <AppShell />,
    errorElement: <RouteErrorBoundary />,
    children: [
      { index: true, element: <Navigate to="/dashboard" replace /> },
      { path: 'dashboard', element: <DashboardPage /> },
      { path: 'cases', element: <CasesPage /> },
      { path: 'cases/new', element: <NewCasePage /> },
      { path: 'cases/:caseUuid', element: <CaseWorkspacePage /> },
      { path: 'help', element: <HelpPage /> },
      { path: '*', element: <NotFoundPage /> },
    ],
  },
]
