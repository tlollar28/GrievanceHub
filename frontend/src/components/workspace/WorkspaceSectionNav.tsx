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
    </nav>
  )
}
