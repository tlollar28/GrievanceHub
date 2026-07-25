import { useEffect, useId, useState } from 'react'
import { ApiError } from '../../api/client'
import type { CaseAssetMetadata } from '../../api/types/assets'
import { useCaseAssetsQuery } from '../../features/cases/useCaseAssetsQuery'
import { AssetDetail } from './AssetDetail'
import { AssetList } from './AssetList'
import { UploadPanel } from './UploadPanel'
import styles from './EvidencePanel.module.css'

type Props = {
  caseUuid: string
  uploadedBy?: string | null
  readOnly?: boolean
}

const NO_CASE_FILE_RAG =
  'Uploaded evidence is attached as case context. It is not full-text searched like the indexed authority corpus.'

export function EvidencePanel({
  caseUuid,
  uploadedBy,
  readOnly = false,
}: Props) {
  const headingId = useId()
  const assetsQuery = useCaseAssetsQuery(caseUuid, {
    category: 'uploaded_document',
  })
  const [selected, setSelected] = useState<CaseAssetMetadata | null>(null)

  useEffect(() => {
    setSelected(null)
  }, [caseUuid])

  const assets = assetsQuery.data?.assets ?? []
  const errorMessage =
    assetsQuery.isError && !assetsQuery.data
      ? assetsQuery.error instanceof ApiError
        ? assetsQuery.error.message
        : 'Unable to load case evidence.'
      : null

  return (
    <div className={styles.panel}>
      <header className={styles.header}>
        <h2 id={headingId} className={styles.heading}>
          Evidence
        </h2>
        <p className={styles.subhead}>
          Upload and review case-scoped supporting files. Evidence references
          attach to conversation turns; they are not authority-corpus retrieval.
        </p>
        <p className={styles.disclosure} role="note">
          {NO_CASE_FILE_RAG}
        </p>
      </header>

      <div className={styles.grid}>
        <div className={styles.section}>
          <h3 className={styles.sectionHeading}>Case assets</h3>
          <AssetList
            assets={assets}
            selectedAssetUuid={selected?.asset_uuid ?? null}
            loading={assetsQuery.isLoading && !assetsQuery.data}
            errorMessage={errorMessage}
            onRetry={() => {
              void assetsQuery.refetch()
            }}
            onSelect={setSelected}
          />
        </div>

        <div className={styles.sideColumn}>
          <UploadPanel
            caseUuid={caseUuid}
            uploadedBy={uploadedBy}
            disabled={readOnly}
            onUploaded={(asset) => {
              setSelected(asset)
            }}
          />
          <AssetDetail
            asset={selected}
            onClose={selected ? () => setSelected(null) : undefined}
          />
        </div>
      </div>
    </div>
  )
}
