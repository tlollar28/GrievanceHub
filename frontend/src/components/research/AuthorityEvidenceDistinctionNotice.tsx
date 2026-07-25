import styles from './SourcesResearch.module.css'

const DEFAULT_NOTICE =
  'Sources Research searches the indexed authority corpus. Files uploaded under Evidence are case attachments and are not part of authority-corpus retrieval.'

type Props = {
  notice?: string
}

export function AuthorityEvidenceDistinctionNotice({
  notice = DEFAULT_NOTICE,
}: Props) {
  return (
    <p className={styles.authorityNotice} data-testid="authority-evidence-notice">
      {notice}
    </p>
  )
}
