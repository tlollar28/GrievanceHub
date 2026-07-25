import type { CaseAssetMetadata } from '../../api/types/assets'
import { formatFileSize } from '../../features/cases/assetValidation'
import styles from './EvidencePanel.module.css'

type Props = {
  assets: CaseAssetMetadata[]
  selectedAssetUuid?: string | null
  onSelect: (asset: CaseAssetMetadata) => void
  loading?: boolean
  errorMessage?: string | null
  onRetry?: () => void
}

function filename(asset: CaseAssetMetadata): string {
  return asset.original_filename?.trim() || 'Untitled upload'
}

export function AssetList({
  assets,
  selectedAssetUuid,
  onSelect,
  loading = false,
  errorMessage,
  onRetry,
}: Props) {
  if (loading) {
    return (
      <div className={styles.skeleton} role="status" aria-busy="true">
        Loading case evidence…
      </div>
    )
  }

  if (errorMessage) {
    return (
      <div className={styles.errorBox} role="alert">
        <p>{errorMessage}</p>
        {onRetry ? (
          <button type="button" className={styles.retryButton} onClick={onRetry}>
            Retry
          </button>
        ) : null}
      </div>
    )
  }

  if (assets.length === 0) {
    return (
      <div className={styles.empty} role="status">
        No evidence uploaded for this case yet.
      </div>
    )
  }

  return (
    <div className={styles.tableWrap}>
      <table className={styles.table}>
        <caption className={styles.caption}>Case evidence assets</caption>
        <thead>
          <tr>
            <th scope="col">Filename</th>
            <th scope="col">Category</th>
            <th scope="col">Type</th>
            <th scope="col">Size</th>
            <th scope="col">Uploaded</th>
            <th scope="col">Details</th>
          </tr>
        </thead>
        <tbody>
          {assets.map((asset) => {
            const selected = asset.asset_uuid === selectedAssetUuid
            const stamp = asset.created_at
              ? new Date(asset.created_at).toLocaleString()
              : '—'
            return (
              <tr
                key={asset.asset_uuid}
                data-selected={selected || undefined}
              >
                <td>
                  <span className={styles.filename}>{filename(asset)}</span>
                  <p className={styles.meta}>{asset.asset_uuid}</p>
                </td>
                <td>{asset.asset_category || '—'}</td>
                <td>{asset.mime_type || '—'}</td>
                <td>{formatFileSize(asset.file_size)}</td>
                <td>
                  {asset.created_at ? (
                    <time dateTime={asset.created_at}>{stamp}</time>
                  ) : (
                    '—'
                  )}
                </td>
                <td>
                  <button
                    type="button"
                    className={styles.detailButton}
                    aria-pressed={selected}
                    aria-label={`View metadata for ${filename(asset)}`}
                    onClick={() => onSelect(asset)}
                  >
                    {selected ? 'Selected' : 'View'}
                  </button>
                </td>
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}
