import { NavLink } from 'react-router-dom'
import styles from './WorkspaceSectionNav.module.css'

type Props = {
  caseUuid: string
}

export function WorkspaceSectionNav({ caseUuid }: Props) {
  return (
    <nav className={styles.nav} aria-label="Case workspace sections">
      <NavLink
        to={`/cases/${caseUuid}/conversation`}
        className={({ isActive }) =>
          `${styles.link}${isActive ? ` ${styles.active}` : ''}`
        }
      >
        Conversation
      </NavLink>
      <NavLink
        to={`/cases/${caseUuid}/evidence`}
        className={({ isActive }) =>
          `${styles.link}${isActive ? ` ${styles.active}` : ''}`
        }
      >
        Evidence
      </NavLink>
      <NavLink
        to={`/cases/${caseUuid}/analysis`}
        className={({ isActive }) =>
          `${styles.link}${isActive ? ` ${styles.active}` : ''}`
        }
      >
        Analysis
      </NavLink>
      <NavLink
        to={`/cases/${caseUuid}/grievance`}
        className={({ isActive }) =>
          `${styles.link}${isActive ? ` ${styles.active}` : ''}`
        }
      >
        Grievance
      </NavLink>
      <NavLink
        to={`/cases/${caseUuid}/artifacts`}
        className={({ isActive }) =>
          `${styles.link}${isActive ? ` ${styles.active}` : ''}`
        }
      >
        Artifacts & History
      </NavLink>
      <NavLink
        to={`/cases/${caseUuid}/workflow`}
        className={({ isActive }) =>
          `${styles.link}${isActive ? ` ${styles.active}` : ''}`
        }
      >
        Workflow
      </NavLink>
      <NavLink
        to={`/cases/${caseUuid}/research`}
        className={({ isActive }) =>
          `${styles.link}${isActive ? ` ${styles.active}` : ''}`
        }
      >
        Sources Research
      </NavLink>
    </nav>
  )
}
