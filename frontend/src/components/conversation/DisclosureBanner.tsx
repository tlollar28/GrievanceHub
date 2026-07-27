import styles from './ConversationPanel.module.css'

type Props = {
  disclosures: string[]
}

export function DisclosureBanner({ disclosures }: Props) {
  if (disclosures.length === 0) {
    return null
  }

  return (
    <div>
      {disclosures.map((text) => (
        <p key={text} className={styles.disclosure} role="status">
          {text}
        </p>
      ))}
    </div>
  )
}
