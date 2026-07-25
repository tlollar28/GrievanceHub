import { Navigate, type RouteObject } from 'react-router-dom'
import { AppShell } from '../components/AppShell'
import { RouteErrorBoundary } from '../components/RouteErrorBoundary'
import { CaseAnalysisPage } from '../routes/CaseAnalysisPage'
import { CaseArtifactsPage } from '../routes/CaseArtifactsPage'
import { CaseConversationPage } from '../routes/CaseConversationPage'
import { CaseEvidencePage } from '../routes/CaseEvidencePage'
import { CaseGrievancePage } from '../routes/CaseGrievancePage'
import {
  CaseWorkspaceIndexRedirect,
  CaseWorkspacePage,
} from '../routes/CaseWorkspacePage'
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
      {
        path: 'cases/:caseUuid',
        element: <CaseWorkspacePage />,
        children: [
          { index: true, element: <CaseWorkspaceIndexRedirect /> },
          { path: 'conversation', element: <CaseConversationPage /> },
          { path: 'evidence', element: <CaseEvidencePage /> },
          { path: 'analysis', element: <CaseAnalysisPage /> },
          { path: 'grievance', element: <CaseGrievancePage /> },
          { path: 'artifacts', element: <CaseArtifactsPage /> },
        ],
      },
      { path: 'help', element: <HelpPage /> },
      { path: '*', element: <NotFoundPage /> },
    ],
  },
]
