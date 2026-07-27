import type { ProgressionMilestone } from '../../features/workflow/workflowLabels'
import styles from './WorkflowPanel.module.css'

type Props = {
  milestones: ProgressionMilestone[]
}

function statusClass(status: ProgressionMilestone['status']): string {
  switch (status) {
    case 'current':
      return styles.milestoneCurrent
    case 'completed':
      return styles.milestoneCompleted
    case 'unavailable':
      return styles.milestoneUnavailable
    default:
      return styles.milestoneFuture
  }
}

function statusText(status: ProgressionMilestone['status']): string {
  switch (status) {
    case 'current':
      return 'Current'
    case 'completed':
      return 'Completed'
    case 'unavailable':
      return 'Unavailable'
    default:
      return 'Upcoming'
  }
}

export function WorkflowProgression({ milestones }: Props) {
  return (
    <ol className={styles.milestoneList} aria-label="Case progression">
      {milestones.map((milestone) => (
        <li
          key={milestone.id}
          className={`${styles.milestone} ${statusClass(milestone.status)}`}
          aria-current={milestone.status === 'current' ? 'step' : undefined}
        >
          <span className={styles.statusTag}>{statusText(milestone.status)}</span>
          <div className={styles.milestoneBody}>
            <p className={styles.milestoneLabel}>{milestone.label}</p>
            <p className={styles.milestoneDetail}>{milestone.detail}</p>
          </div>
        </li>
      ))}
    </ol>
  )
}
