import { useState, type FormEvent } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { ConnectionStatus } from './ConnectionStatus'
import { EnvironmentBadge } from './EnvironmentBadge'
import styles from './TopBar.module.css'

export function TopBar() {
  const navigate = useNavigate()
  const [searchValue, setSearchValue] = useState('')

  function onSearchSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const trimmed = searchValue.trim()
    const params = new URLSearchParams()
    if (trimmed) {
      params.set('search', trimmed)
    }
    const query = params.toString()
    void navigate(query ? `/cases?${query}` : '/cases')
  }

  return (
    <header className={styles.header}>
      <div className={styles.brandBlock}>
        <Link to="/dashboard" className={styles.brand}>
          GrievanceHub
        </Link>
        <span className={styles.productHint}>Steward workspace</span>
      </div>

      <form
        className={styles.search}
        role="search"
        aria-label="Search saved cases"
        onSubmit={onSearchSubmit}
      >
        <label className={styles.visuallyHidden} htmlFor="global-case-search">
          Search saved cases
        </label>
        <input
          id="global-case-search"
          type="search"
          className={styles.searchInput}
          value={searchValue}
          onChange={(event) => setSearchValue(event.target.value)}
          placeholder="Search cases"
          autoComplete="off"
        />
        <button type="submit" className={styles.searchButton}>
          Search
        </button>
      </form>

      <div className={styles.meta}>
        <EnvironmentBadge />
        <ConnectionStatus />
      </div>
    </header>
  )
}
