import { Link } from 'react-router-dom'
import styles from './pages.module.css'

export function NotFoundPage() {
  return (
    <section className={styles.page} aria-labelledby="not-found-heading">
      <h1 id="not-found-heading">Page not found</h1>
      <p>
        The requested route is not part of the current GrievanceHub steward
        workspace shell.
      </p>
      <p>
        <Link to="/dashboard">Return to Dashboard</Link>
      </p>
    </section>
  )
}
