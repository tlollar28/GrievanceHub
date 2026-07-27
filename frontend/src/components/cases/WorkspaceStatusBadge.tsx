import styles from './WorkspaceStatusBadge.module.css'
import type { SavedCaseWorkspaceStatus } from '../../api/types/savedCases'
import { formatWorkspaceStatus } from '../../features/cases/savedCaseFilters'

const STATUS_CLASS: Record<SavedCaseWorkspaceStatus, string> = {
  open: styles.open,
  closed: styles.closed,
  reopened: styles.reopened,
  appealed: styles.appealed,
  settled: styles.settled,
  archived: styles.archived,
}

type Props = {
  status: SavedCaseWorkspaceStatus
}

export function WorkspaceStatusBadge({ status }: Props) {
  return (
    <span className={`${styles.badge} ${STATUS_CLASS[status]}`}>
      {formatWorkspaceStatus(status)}
    </span>
  )
}
