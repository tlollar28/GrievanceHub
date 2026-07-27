import { NavLink } from 'react-router-dom'
import styles from './SideNav.module.css'

type NavItem = {
  to: string
  label: string
  end?: boolean
}

const NAV_ITEMS: NavItem[] = [
  { to: '/dashboard', label: 'Dashboard' },
  { to: '/cases', label: 'Cases', end: true },
  { to: '/cases/new', label: 'New Case' },
  { to: '/help', label: 'Help' },
]

export function SideNav() {
  return (
    <aside className={styles.aside} aria-label="Primary">
      <nav className={styles.nav} aria-label="Primary navigation">
        <ul className={styles.list}>
          {NAV_ITEMS.map((item) => (
            <li key={item.to}>
              <NavLink
                to={item.to}
                end={item.end}
                className={({ isActive }) =>
                  isActive ? `${styles.link} ${styles.active}` : styles.link
                }
              >
                {item.label}
              </NavLink>
            </li>
          ))}
        </ul>
      </nav>
    </aside>
  )
}
