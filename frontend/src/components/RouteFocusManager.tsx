import { useEffect } from 'react'
import { useLocation } from 'react-router-dom'

/**
 * Move keyboard focus to the page-level heading after navigation.
 * Prefer the first h1 inside main; fall back to the main landmark.
 */
export function RouteFocusManager() {
  const location = useLocation()

  useEffect(() => {
    const main = document.getElementById('main-content')
    if (!main) return
    const heading =
      main.querySelector<HTMLElement>('#case-workspace-heading, h1') ?? main
    if (heading.tabIndex < 0) {
      heading.tabIndex = -1
    }
    heading.focus()
  }, [location.pathname])

  return null
}
