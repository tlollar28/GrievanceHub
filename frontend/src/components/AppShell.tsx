import { Outlet } from 'react-router-dom'
import { RouteFocusManager } from './RouteFocusManager'
import { SideNav } from './SideNav'
import { SkipToContent } from './SkipToContent'
import { TopBar } from './TopBar'
import styles from './AppShell.module.css'

export function AppShell() {
  return (
    <div className={styles.shell}>
      <SkipToContent />
      <TopBar />
      <div className={styles.body}>
        <SideNav />
        <main id="main-content" className={styles.main} tabIndex={-1}>
          <RouteFocusManager />
          <Outlet />
        </main>
      </div>
    </div>
  )
}
