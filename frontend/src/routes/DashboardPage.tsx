import styles from './pages.module.css'

export function DashboardPage() {
  return (
    <section className={styles.page} aria-labelledby="dashboard-heading">
      <h1 id="dashboard-heading">Dashboard</h1>
      <p>
        Steward home for Saved Cases. This route is part of the W6 shell
        foundation.
      </p>
      <p className={styles.statusNote}>
        Implementation status: M0 complete. Saved Cases listing arrives in M1.
      </p>
    </section>
  )
}
