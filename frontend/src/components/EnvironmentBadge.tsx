import styles from './EnvironmentBadge.module.css'

export function EnvironmentBadge() {
  return (
    <span className={styles.badge} title="Local development environment">
      Local
    </span>
  )
}
