import { Link } from 'react-router-dom'
import { ConnectionStatus } from './ConnectionStatus'
import { EnvironmentBadge } from './EnvironmentBadge'
import styles from './TopBar.module.css'

export function TopBar() {
  return (
    <header className={styles.header}>
      <div className={styles.brandBlock}>
        <Link to="/dashboard" className={styles.brand}>
          GrievanceHub
        </Link>
        <span className={styles.productHint}>Steward workspace</span>
      </div>
      <div className={styles.meta}>
        <EnvironmentBadge />
        <ConnectionStatus />
      </div>
    </header>
  )
}
