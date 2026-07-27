import { isRouteErrorResponse, Link, useRouteError } from 'react-router-dom'
import styles from '../routes/pages.module.css'

export function RouteErrorBoundary() {
  const error = useRouteError()

  let title = 'Page unavailable'
  let detail =
    'This page could not be displayed. Return to the dashboard and try again.'

  if (isRouteErrorResponse(error)) {
    if (error.status === 404) {
      title = 'Page not found'
      detail = 'The requested page does not exist or is no longer available.'
    } else if (error.status === 403) {
      title = 'Page unavailable'
      detail = 'This page is not available for the current session.'
    } else if (error.status >= 500) {
      detail =
        'The application could not load this page right now. Return to the dashboard and try again.'
    }
  }

  return (
    <section
      className={styles.page}
      aria-labelledby="route-error-heading"
      role="alert"
    >
      <h1 id="route-error-heading">{title}</h1>
      <p>{detail}</p>
      <p>
        <Link to="/dashboard">Return to Dashboard</Link>
      </p>
    </section>
  )
}
