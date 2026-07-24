import styles from './pages.module.css'

export function NewCasePage() {
  return (
    <section className={styles.page} aria-labelledby="new-case-heading">
      <h1 id="new-case-heading">New Case</h1>
      <p>
        Case creation belongs to a later W6 milestone. This page is a navigation
        placeholder only.
      </p>
      <p className={styles.statusNote}>
        Implementation status: not started. Do not submit case data from this
        screen yet.
      </p>
    </section>
  )
}
