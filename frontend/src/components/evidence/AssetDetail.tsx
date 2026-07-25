import type { CaseAssetMetadata } from '../../api/types/assets'
import { formatFileSize } from '../../features/cases/assetValidation'
import styles from './EvidencePanel.module.css'

type Props = {
  asset: CaseAssetMetadata | null
  onClose?: () => void
}

function displayName(asset: CaseAssetMetadata): string {
  return asset.original_filename?.trim() || asset.asset_uuid
}

/**
 * Safe metadata presentation. Never renders stored_path or stored_filename.
 */
export function AssetDetail({ asset, onClose }: Props) {
  if (!asset) {
    return (
      <section
        className={styles.section}
        aria-labelledby="asset-detail-heading"
      >
        <h3 id="asset-detail-heading" className={styles.sectionHeading}>
          Asset detail
        </h3>
        <p className={styles.empty} role="status">
          Select an asset to view metadata.
        </p>
      </section>
    )
  }

  const rows: Array<{ label: string; value: string; mono?: boolean }> = [
    { label: 'Filename', value: displayName(asset) },
    { label: 'Asset UUID', value: asset.asset_uuid, mono: true },
    { label: 'Category', value: String(asset.asset_category || '—') },
    { label: 'MIME type', value: asset.mime_type || '—' },
    { label: 'File size', value: formatFileSize(asset.file_size) },
    { label: 'SHA-256', value: asset.sha256 || '—', mono: true },
    { label: 'Uploaded by', value: asset.uploaded_by || '—' },
    { label: 'Source', value: String(asset.source || '—') },
    { label: 'Status', value: String(asset.status || '—') },
    {
      label: 'Created',
      value: asset.created_at
        ? new Date(asset.created_at).toLocaleString()
        : '—',
    },
  ]

  return (
    <section
      className={styles.section}
      aria-labelledby="asset-detail-heading"
    >
      <div className={styles.header}>
        <h3 id="asset-detail-heading" className={styles.sectionHeading}>
          Asset detail
        </h3>
        {onClose ? (
          <button
            type="button"
            className={styles.secondaryButton}
            onClick={onClose}
          >
            Clear selection
          </button>
        ) : null}
      </div>
      <dl className={styles.detailList}>
        {rows.map((row) => (
          <div key={row.label}>
            <dt>{row.label}</dt>
            <dd className={row.mono ? styles.mono : undefined}>{row.value}</dd>
          </div>
        ))}
      </dl>
      <p className={styles.statusText}>
        Metadata only — file body is not previewed in this milestone.
      </p>
    </section>
  )
}
