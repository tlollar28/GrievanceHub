import { useEffect, useId, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { ApiError } from '../../api/client'
import type {
  ArtifactSortOrder,
  ArtifactTypeFilter,
  HistoryOrder,
} from '../../api/types/artifacts'
import {
  applyArtifactLibraryState,
  parseArtifactLibraryState,
  sortArtifacts,
} from '../../features/artifacts/artifactLibraryFilters'
import { useCaseArtifactsQuery } from '../../features/cases/useCaseArtifactsQuery'
import { ArtifactComparePanel } from './ArtifactComparePanel'
import { ArtifactDetail } from './ArtifactDetail'
import { ArtifactLibraryList } from './ArtifactLibraryList'
import { CaseTimelinePanel } from './CaseTimelinePanel'
import { HistoryContextDialog } from './HistoryContextDialog'
import { OfficialCaseRecord } from './OfficialCaseRecord'
import styles from './ArtifactsPanel.module.css'

type Props = {
  caseUuid: string
}

export function ArtifactsPanel({ caseUuid }: Props) {
  const headingId = useId()
  const [searchParams, setSearchParams] = useSearchParams()
  const urlState = parseArtifactLibraryState(searchParams)

  const listFilters =
    urlState.type === 'all'
      ? {}
      : { artifact_type: urlState.type as Exclude<ArtifactTypeFilter, 'all'> }

  const artifactsQuery = useCaseArtifactsQuery(caseUuid, listFilters)
  const artifacts = sortArtifacts(
    artifactsQuery.data?.artifacts ?? [],
    urlState.sort,
  )

  const [compareLeft, setCompareLeft] = useState<string | null>(null)
  const [compareRight, setCompareRight] = useState<string | null>(null)
  const [contextEventId, setContextEventId] = useState<string | null>(null)

  useEffect(() => {
    setCompareLeft(null)
    setCompareRight(null)
    setContextEventId(null)
  }, [caseUuid])

  useEffect(() => {
    if (!urlState.artifact) return
    const exists = artifacts.some(
      (item) => item.artifact_uuid === urlState.artifact,
    )
    if (!exists && artifactsQuery.isSuccess) {
      setSearchParams(
        applyArtifactLibraryState(searchParams, { artifact: null }),
        { replace: true },
      )
    }
  }, [
    artifacts,
    artifactsQuery.isSuccess,
    searchParams,
    setSearchParams,
    urlState.artifact,
  ])

  function updateUrl(partial: Parameters<typeof applyArtifactLibraryState>[1]) {
    setSearchParams(applyArtifactLibraryState(searchParams, partial), {
      replace: true,
    })
  }

  function toggleCompare(artifactUuid: string) {
    if (compareLeft === artifactUuid) {
      setCompareLeft(null)
      return
    }
    if (compareRight === artifactUuid) {
      setCompareRight(null)
      return
    }
    if (!compareLeft) {
      setCompareLeft(artifactUuid)
      return
    }
    if (!compareRight) {
      if (compareLeft === artifactUuid) return
      setCompareRight(artifactUuid)
      return
    }
    // Replace right when both already selected.
    setCompareRight(artifactUuid)
  }

  const listError =
    artifactsQuery.isError && !artifactsQuery.data
      ? artifactsQuery.error instanceof ApiError
        ? artifactsQuery.error.message
        : 'Unable to load official artifacts.'
      : null

  return (
    <div className={styles.panel}>
      <header className={styles.header}>
        <h2 id={headingId} className={styles.heading}>
          Artifacts &amp; History
        </h2>
        <p className={styles.subhead}>
          Browse official saved analysis reports and grievance forms for this
          case, review the Official Case Record and timeline, compare compatible
          artifacts, and jump to nearby read-only context.
        </p>
        <p className={styles.disclosure} role="note">
          Browsing, comparing, and opening context do not create artifacts,
          PDFs, versions, or timeline events. Workflow outcomes and Sources
          administration are not part of this screen.
        </p>
      </header>

      <div className={styles.toolbar} role="group" aria-label="Artifact filters">
        <div className={styles.field}>
          <label className={styles.fieldLabel} htmlFor="artifact-type-filter">
            Artifact type
          </label>
          <select
            id="artifact-type-filter"
            className={styles.select}
            value={urlState.type}
            onChange={(event) =>
              updateUrl({
                type: event.target.value as ArtifactTypeFilter,
                artifact: null,
              })
            }
          >
            <option value="all">All official artifacts</option>
            <option value="analysis_report">Analysis reports</option>
            <option value="grievance_form">Grievance forms</option>
          </select>
        </div>
        <div className={styles.field}>
          <label className={styles.fieldLabel} htmlFor="artifact-sort">
            Sort
          </label>
          <select
            id="artifact-sort"
            className={styles.select}
            value={urlState.sort}
            onChange={(event) =>
              updateUrl({ sort: event.target.value as ArtifactSortOrder })
            }
          >
            <option value="newest">Newest first</option>
            <option value="oldest">Oldest first</option>
          </select>
        </div>
      </div>

      <div className={styles.grid}>
        <section
          className={styles.section}
          aria-labelledby="artifact-library-heading"
        >
          <h3 id="artifact-library-heading" className={styles.sectionHeading}>
            Artifact Library
          </h3>
          <ArtifactLibraryList
            artifacts={artifacts}
            selectedArtifactUuid={urlState.artifact}
            compareLeft={compareLeft}
            compareRight={compareRight}
            loading={artifactsQuery.isLoading && !artifactsQuery.data}
            errorMessage={listError}
            onRetry={() => {
              void artifactsQuery.refetch()
            }}
            onSelect={(artifactUuid) => updateUrl({ artifact: artifactUuid })}
            onToggleCompare={toggleCompare}
          />
        </section>

        <section
          className={styles.section}
          aria-labelledby="artifact-detail-heading"
        >
          <h3 id="artifact-detail-heading" className={styles.sectionHeading}>
            Artifact detail
          </h3>
          <ArtifactDetail
            caseUuid={caseUuid}
            artifactUuid={urlState.artifact}
          />
        </section>
      </div>

      <ArtifactComparePanel
        caseUuid={caseUuid}
        artifacts={artifacts}
        leftUuid={compareLeft}
        rightUuid={compareRight}
        onClear={() => {
          setCompareLeft(null)
          setCompareRight(null)
        }}
      />

      <OfficialCaseRecord
        caseUuid={caseUuid}
        order={urlState.historyOrder}
        onOrderChange={(historyOrder: HistoryOrder) =>
          updateUrl({ historyOrder })
        }
        onJumpToContext={setContextEventId}
        onOpenArtifact={(artifactUuid) => updateUrl({ artifact: artifactUuid })}
      />

      <CaseTimelinePanel
        caseUuid={caseUuid}
        order={urlState.timelineOrder}
        onOrderChange={(timelineOrder: HistoryOrder) =>
          updateUrl({ timelineOrder })
        }
      />

      <HistoryContextDialog
        caseUuid={caseUuid}
        eventId={contextEventId}
        onClose={() => setContextEventId(null)}
      />
    </div>
  )
}
