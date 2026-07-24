import { isRouteErrorResponse, Link, useRouteError } from 'react-router-dom'
import styles from '../routes/pages.module.css'

export function RouteErrorBoundary() {
  const error = useRouteError()

  let title = 'Something went wrong'
  let detail = 'An unexpected error occurred while rendering this page.'

  if (isRouteErrorResponse(error)) {
    title = error.status === 404 ? 'Page not found' : `Error ${error.status}`
    detail =
      typeof error.data === 'string' && error.data.trim().length > 0
        ? error.data
        : error.statusText || detail
  } else if (error instanceof Error && error.message) {
    detail = error.message
  }

  return (
    <section className={styles.page} aria-labelledby="route-error-heading">
      <h1 id="route-error-heading">{title}</h1>
      <p>{detail}</p>
      <p>
        <Link to="/dashboard">Return to Dashboard</Link>
      </p>
    </section>
  )
}
