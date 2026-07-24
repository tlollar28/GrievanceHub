import styles from './pages.module.css'

export function HelpPage() {
  return (
    <section className={styles.page} aria-labelledby="help-heading">
      <h1 id="help-heading">Help</h1>
      <p>
        GrievanceHub is a steward case workspace. The application manages
        workflow automation; the steward manages the grievance.
      </p>
      <p>
        Normal chat never creates analysis reports or grievances. Those require
        explicit Generate actions in later milestones.
      </p>
      <p className={styles.statusNote}>
        Implementation status: M0 help stub. Expanded workflow guidance arrives
        with later W6 milestones.
      </p>
    </section>
  )
}
