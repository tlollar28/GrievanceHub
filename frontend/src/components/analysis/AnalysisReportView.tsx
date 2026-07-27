import type { GrievanceHubReportData } from '../../api/types/reports'
import { AuthoritySection } from './AuthoritySection'
import { CitationValidationSummary } from './CitationValidationSummary'
import { LimitationsPanel } from './LimitationsPanel'
import styles from './AnalysisPanel.module.css'

type Props = {
  report: GrievanceHubReportData
  mode: 'temporary' | 'saved'
  versionNumber?: number | null
  suggestedVersionNumber?: number | null
  retrievalGaps?: Record<string, unknown> | null
}

function formatWhen(value: string | undefined): string | null {
  if (!value?.trim()) return null
  const parsed = Date.parse(value)
  if (Number.isNaN(parsed)) return value
  return new Date(parsed).toLocaleString()
}

export function AnalysisReportView({
  report,
  mode,
  versionNumber,
  suggestedVersionNumber,
  retrievalGaps,
}: Props) {
  const title =
    report.report_title?.trim() ||
    (mode === 'temporary' ? 'Temporary analysis preview' : 'Saved analysis')
  const assessment = report.quick_assessment
  const remedy = report.recommended_remedy
  const detailed = report.detailed_analysis
  const evidence = report.supporting_evidence ?? []
  const secondary = (report.secondary_issues ?? []).filter(
    (s) => s.trim().length > 0,
  )

  return (
    <article className={styles.report} aria-label={title}>
      <header className={styles.reportHeader}>
        <div className={styles.metaRow}>
          {mode === 'temporary' ? (
            <span className={styles.tempBadge}>Temporary preview</span>
          ) : (
            <span className={styles.officialBadge}>Official saved version</span>
          )}
          {mode === 'saved' && versionNumber != null ? (
            <span>Version {versionNumber}</span>
          ) : null}
          {mode === 'temporary' && suggestedVersionNumber != null ? (
            <span>
              Would become version {suggestedVersionNumber} if saved
            </span>
          ) : null}
        </div>
        <h3 className={styles.reportTitle}>{title}</h3>
        <div className={styles.metaRow}>
          {report.brand?.trim() ? <span>{report.brand.trim()}</span> : null}
          {formatWhen(
            typeof report.generated_at === 'string'
              ? report.generated_at
              : undefined,
          ) ? (
            <span>
              Generated{' '}
              {formatWhen(
                typeof report.generated_at === 'string'
                  ? report.generated_at
                  : undefined,
              )}
            </span>
          ) : null}
        </div>
        {report.your_question?.trim() ? (
          <p>
            <strong>Your question: </strong>
            {report.your_question.trim()}
          </p>
        ) : null}
      </header>

      {assessment &&
      (assessment.summary?.trim() ||
        assessment.grievability?.trim() ||
        assessment.why?.trim()) ? (
        <section className={styles.block} aria-label="Quick assessment">
          <p className={styles.kindLabel}>Generated analysis</p>
          <h4 className={styles.blockHeading}>Quick assessment</h4>
          <div className={styles.generated}>
            {assessment.summary?.trim() ? (
              <p>{assessment.summary.trim()}</p>
            ) : null}
            {assessment.grievability?.trim() ? (
              <p>Grievability: {assessment.grievability.trim()}</p>
            ) : null}
            {assessment.confidence?.trim() ? (
              <p>Confidence: {assessment.confidence.trim()}</p>
            ) : null}
            {assessment.why?.trim() ? <p>{assessment.why.trim()}</p> : null}
          </div>
        </section>
      ) : null}

      {secondary.length > 0 ? (
        <section className={styles.block} aria-label="Secondary issues">
          <p className={styles.kindLabel}>Generated analysis</p>
          <h4 className={styles.blockHeading}>Secondary issues</h4>
          <ul className={styles.list}>
            {secondary.map((issue) => (
              <li key={issue}>{issue}</li>
            ))}
          </ul>
        </section>
      ) : null}

      {detailed &&
      (detailed.grievance_framework?.trim() ||
        (detailed.evidence_to_gather ?? []).length > 0 ||
        (detailed.strategic_tips ?? []).length > 0) ? (
        <section className={styles.block} aria-label="Detailed analysis">
          <p className={styles.kindLabel}>Generated analysis</p>
          <h4 className={styles.blockHeading}>Detailed analysis</h4>
          <div className={styles.generated}>
            {detailed.grievance_framework?.trim() ? (
              <p>{detailed.grievance_framework.trim()}</p>
            ) : null}
            {(detailed.evidence_to_gather ?? []).filter((s) => s.trim())
              .length > 0 ? (
              <>
                <h5 className={styles.sectionHeading}>Evidence to gather</h5>
                <ul className={styles.list}>
                  {(detailed.evidence_to_gather ?? [])
                    .filter((s) => s.trim())
                    .map((item) => (
                      <li key={item}>{item}</li>
                    ))}
                </ul>
              </>
            ) : null}
            {(detailed.strategic_tips ?? []).length > 0 ? (
              <>
                <h5 className={styles.sectionHeading}>Strategic tips</h5>
                <ul className={styles.list}>
                  {(detailed.strategic_tips ?? []).map((tip, index) => (
                    <li key={`${tip.title ?? 'tip'}-${index}`}>
                      {tip.title?.trim() ? (
                        <strong>{tip.title.trim()}: </strong>
                      ) : null}
                      {tip.text?.trim() ?? ''}
                    </li>
                  ))}
                </ul>
              </>
            ) : null}
          </div>
        </section>
      ) : null}

      {remedy &&
      ((remedy.statements ?? []).length > 0 ||
        remedy.insufficient_notice?.trim()) ? (
        <section className={styles.block} aria-label="Recommended remedy">
          <p className={styles.kindLabel}>Generated recommendation</p>
          <h4 className={styles.blockHeading}>Recommended remedy</h4>
          <div className={styles.recommendation}>
            {(remedy.statements ?? []).filter((s) => s.trim()).length > 0 ? (
              <ul className={styles.list}>
                {(remedy.statements ?? [])
                  .filter((s) => s.trim())
                  .map((statement) => (
                    <li key={statement}>{statement}</li>
                  ))}
              </ul>
            ) : null}
            {remedy.insufficient_notice?.trim() ? (
              <p>{remedy.insufficient_notice.trim()}</p>
            ) : null}
          </div>
        </section>
      ) : null}

      {evidence.length > 0 ? (
        <section className={styles.block} aria-label="Supporting evidence">
          <p className={styles.kindLabel}>Source excerpt</p>
          <h4 className={styles.blockHeading}>Supporting evidence</h4>
          {evidence.map((item, index) => {
            const quote = item.direct_quote?.trim()
            const supports = item.what_it_supports?.trim()
            const parts: string[] = []
            if (item.document_type?.trim()) parts.push(item.document_type.trim())
            if (item.document_name?.trim()) parts.push(item.document_name.trim())
            if (item.article_or_section?.trim()) {
              parts.push(item.article_or_section.trim())
            }
            if (item.page != null) parts.push(`p. ${item.page}`)
            return (
              <article
                key={`evidence-${index}-${parts.join('-')}`}
                className={styles.evidenceItem}
              >
                {parts.length > 0 ? (
                  <p className={styles.citationRef}>{parts.join(' · ')}</p>
                ) : null}
                {quote ? (
                  <blockquote className={styles.quote}>{quote}</blockquote>
                ) : null}
                {supports ? <p>{supports}</p> : null}
                {item.how_to_use?.trim() ? (
                  <p>{item.how_to_use.trim()}</p>
                ) : null}
              </article>
            )
          })}
        </section>
      ) : null}

      <AuthoritySection
        heading="Key contract violations"
        items={report.key_contract_violations}
      />
      <AuthoritySection
        heading="Union supporting authority"
        items={report.union_supporting_authority}
      />
      <AuthoritySection
        heading="Procedural requirements"
        items={report.procedural_requirements}
      />
      <AuthoritySection
        heading="Information rights"
        items={report.information_rights}
      />
      <AuthoritySection
        heading="Timeline requirements"
        items={report.timeline_requirements}
      />
      <AuthoritySection
        heading="Remedy authority"
        items={report.remedy_authority}
      />
      <AuthoritySection
        heading="Management limiting authority"
        items={report.management_limiting_authority}
      />
      <AuthoritySection
        heading="Background authority"
        items={report.background_authority}
      />

      <LimitationsPanel
        limitations={report.limitations}
        researchDraftNotice={report.research_draft_notice}
        retrievalGaps={retrievalGaps}
      />
      <CitationValidationSummary validation={report.citation_validation} />

      {report.source_references?.found &&
      report.source_references.found.length > 0 ? (
        <section className={styles.block} aria-label="Source references">
          <p className={styles.kindLabel}>Citation reference</p>
          <h4 className={styles.blockHeading}>Source references found</h4>
          <ul className={styles.list}>
            {report.source_references.found.map((ref, index) => (
              <li key={`${ref.source_type ?? 'source'}-${index}`}>
                {ref.source_type?.trim() ? `${ref.source_type}: ` : ''}
                {(ref.document_names ?? []).join(', ') ||
                  `${ref.authority_count ?? 0} authorities`}
              </li>
            ))}
          </ul>
        </section>
      ) : null}
    </article>
  )
}
