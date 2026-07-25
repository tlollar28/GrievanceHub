import type { ReactNode } from 'react'
import type { CaseWorkspace } from '../../api/types/workspace'
import { CaseContextHeader } from './CaseContextHeader'
import { CaseRail } from './CaseRail'
import styles from './CaseWorkspaceShell.module.css'

type Props = {
  workspace: CaseWorkspace
  casesListHref?: string
  factsReadOnly?: boolean
  children?: ReactNode
}

/**
 * Reusable case workspace layout for M2+. Nested M3+ routes can render in the
 * main region without replacing the shell.
 */
export function CaseWorkspaceShell({
  workspace,
  casesListHref,
  factsReadOnly,
  children,
}: Props) {
  return (
    <div className={styles.shell}>
      <CaseContextHeader
        workspace={workspace}
        casesListHref={casesListHref}
      />
      <div className={styles.body}>
        <CaseRail workspace={workspace} factsReadOnly={factsReadOnly} />
        <div className={styles.main}>
          <div className={styles.mainInner}>
            {children}
          </div>
        </div>
      </div>
    </div>
  )
}
