import styles from './pages.module.css'

export function CasesPage() {
  return (
    <section className={styles.page} aria-labelledby="cases-heading">
      <h1 id="cases-heading">Cases</h1>
      <p>
        Full Saved Cases list with filters will live here. No case data is loaded
        in M0.
      </p>
      <p className={styles.statusNote}>
        Implementation status: route shell only. M1 will connect{' '}
        <code>GET /cases/saved</code>.
      </p>
    </section>
  )
}
