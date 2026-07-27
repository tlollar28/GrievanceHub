import { useEffect, useId, useRef, useState } from 'react'
import { ApiError } from '../../api/client'
import type { CaseAssetMetadata } from '../../api/types/assets'
import { formatFileSize } from '../../features/cases/assetValidation'
import { useCaseAssetsQuery } from '../../features/cases/useCaseAssetsQuery'
import styles from './ConversationPanel.module.css'

type Props = {
  caseUuid: string
  selectedAssetUuids: string[]
  disabled?: boolean
  onChange: (assetUuids: string[]) => void
}

const DISCLOSURE =
  'Uploaded evidence is attached as case context. It is not full-text searched like the indexed authority corpus.'

function assetLabel(asset: CaseAssetMetadata): string {
  return asset.original_filename?.trim() || asset.asset_uuid
}

export function AttachmentPicker({
  caseUuid,
  selectedAssetUuids,
  disabled = false,
  onChange,
}: Props) {
  const headingId = useId()
  const listId = useId()
  const disclosureId = useId()
  const countId = useId()
  const openButtonRef = useRef<HTMLButtonElement>(null)
  const dialogRef = useRef<HTMLDivElement>(null)
  const [open, setOpen] = useState(false)
  const assetsQuery = useCaseAssetsQuery(
    caseUuid,
    { category: 'uploaded_document' },
    open || selectedAssetUuids.length > 0,
  )

  useEffect(() => {
    setOpen(false)
  }, [caseUuid])

  useEffect(() => {
    if (!open) {
      return
    }
    const firstCheckbox = dialogRef.current?.querySelector<HTMLElement>(
      'input[type="checkbox"]',
    )
    firstCheckbox?.focus()
  }, [open, assetsQuery.dataUpdatedAt])

  function closePicker() {
    setOpen(false)
    openButtonRef.current?.focus()
  }

  function toggleAsset(assetUuid: string) {
    if (selectedAssetUuids.includes(assetUuid)) {
      onChange(selectedAssetUuids.filter((id) => id !== assetUuid))
      return
    }
    onChange([...selectedAssetUuids, assetUuid])
  }

  const assets = assetsQuery.data?.assets ?? []
  const selectedAssets = assets.filter((asset) =>
    selectedAssetUuids.includes(asset.asset_uuid),
  )
  // Keep labels for selected ids even if list filter temporarily empty after switch.
  const orphanSelected = selectedAssetUuids.filter(
    (id) => !selectedAssets.some((asset) => asset.asset_uuid === id),
  )

  return (
    <div className={styles.attachmentBlock}>
      <p id={disclosureId} className={styles.attachmentDisclosure}>
        {DISCLOSURE}
      </p>

      <div className={styles.attachmentToolbar}>
        <button
          ref={openButtonRef}
          type="button"
          className={styles.attachButton}
          disabled={disabled}
          aria-expanded={open}
          aria-controls={listId}
          onClick={() => setOpen((value) => !value)}
        >
          Attach case evidence
        </button>
        <p id={countId} className={styles.attachmentCount} role="status">
          {selectedAssetUuids.length === 0
            ? 'No evidence attached'
            : `${selectedAssetUuids.length} evidence reference${
                selectedAssetUuids.length === 1 ? '' : 's'
              } selected`}
        </p>
      </div>

      {selectedAssetUuids.length > 0 ? (
        <ul className={styles.selectedAttachments} aria-labelledby={countId}>
          {selectedAssets.map((asset) => (
            <li key={asset.asset_uuid}>
              <span>
                {assetLabel(asset)}
                {asset.file_size != null
                  ? ` (${formatFileSize(asset.file_size)})`
                  : ''}
              </span>
              <button
                type="button"
                className={styles.removeAttachment}
                disabled={disabled}
                aria-label={`Remove ${assetLabel(asset)}`}
                onClick={() =>
                  onChange(
                    selectedAssetUuids.filter((id) => id !== asset.asset_uuid),
                  )
                }
              >
                Remove
              </button>
            </li>
          ))}
          {orphanSelected.map((assetUuid) => (
            <li key={assetUuid}>
              <span>{assetUuid}</span>
              <button
                type="button"
                className={styles.removeAttachment}
                disabled={disabled}
                aria-label={`Remove ${assetUuid}`}
                onClick={() =>
                  onChange(selectedAssetUuids.filter((id) => id !== assetUuid))
                }
              >
                Remove
              </button>
            </li>
          ))}
        </ul>
      ) : null}

      {open ? (
        <div
          ref={dialogRef}
          id={listId}
          className={styles.attachmentPicker}
          role="region"
          aria-labelledby={headingId}
          aria-describedby={disclosureId}
        >
          <div className={styles.attachmentPickerHeader}>
            <h3 id={headingId} className={styles.attachmentPickerHeading}>
              Current-case evidence
            </h3>
            <button
              type="button"
              className={styles.attachButton}
              onClick={closePicker}
            >
              Close
            </button>
          </div>

          {assetsQuery.isLoading && !assetsQuery.data ? (
            <p className={styles.attachmentStatus} role="status">
              Loading case evidence…
            </p>
          ) : null}

          {assetsQuery.isError && !assetsQuery.data ? (
            <div className={styles.errorBox} role="alert">
              <p>
                {assetsQuery.error instanceof ApiError
                  ? assetsQuery.error.message
                  : 'Unable to load case evidence.'}
              </p>
              <button
                type="button"
                className={styles.retryButton}
                onClick={() => {
                  void assetsQuery.refetch()
                }}
              >
                Retry
              </button>
            </div>
          ) : null}

          {assetsQuery.data && assets.length === 0 ? (
            <p className={styles.attachmentStatus} role="status">
              No uploaded evidence on this case yet. Upload files on the
              Evidence page first.
            </p>
          ) : null}

          {assets.length > 0 ? (
            <ul className={styles.attachmentChoices}>
              {assets.map((asset) => {
                const checked = selectedAssetUuids.includes(asset.asset_uuid)
                const inputId = `attach-${asset.asset_uuid}`
                return (
                  <li key={asset.asset_uuid}>
                    <label htmlFor={inputId} className={styles.attachmentChoice}>
                      <input
                        id={inputId}
                        type="checkbox"
                        checked={checked}
                        disabled={disabled}
                        onChange={() => toggleAsset(asset.asset_uuid)}
                      />
                      <span>
                        {assetLabel(asset)}
                        <span className={styles.attachmentMeta}>
                          {' '}
                          · {asset.mime_type || 'unknown type'} ·{' '}
                          {formatFileSize(asset.file_size)}
                        </span>
                      </span>
                    </label>
                  </li>
                )
              })}
            </ul>
          ) : null}
        </div>
      ) : null}
    </div>
  )
}
