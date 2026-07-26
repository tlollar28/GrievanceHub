import { useId, useMemo } from 'react'
import type { TemporaryGrievanceDraft } from '../../api/types/grievances'
import type { DraftValidationView } from '../../features/grievance/draftValidation'
import {
  getTemplateFields,
  stepTypeLabel,
  templateDisplayName,
  type TemplateFieldMeta,
} from '../../features/grievance/templateFields'
import { DraftValidationSummary } from './DraftValidationSummary'
import { GrievanceSaveActions } from './GrievanceSaveActions'
import styles from './GrievancePanel.module.css'

type Props = {
  draft: TemporaryGrievanceDraft
  validation: DraftValidationView
  busy: boolean
  busyMode: 'save' | 'save_and_print' | null
  highlightInvalid: boolean
  onChangeField: (fieldId: string, value: string) => void
  onSave: () => void
  onSaveAndPrint: () => void
  onCancel: () => void
  onValidate: () => void
}

function groupBySection(
  fields: readonly TemplateFieldMeta[],
): Array<{ section: string; fields: TemplateFieldMeta[] }> {
  const order: string[] = []
  const map = new Map<string, TemplateFieldMeta[]>()
  for (const field of fields) {
    if (!map.has(field.section)) {
      map.set(field.section, [])
      order.push(field.section)
    }
    map.get(field.section)!.push(field)
  }
  return order.map((section) => ({
    section,
    fields: map.get(section)!,
  }))
}

export function GrievanceDraftEditor({
  draft,
  validation,
  busy,
  busyMode,
  highlightInvalid,
  onChangeField,
  onSave,
  onSaveAndPrint,
  onCancel,
  onValidate,
}: Props) {
  const headingId = useId()
  const dirty = draft.steward_override_field_ids.length > 0
  const sections = useMemo(
    () => groupBySection(getTemplateFields(draft.template_id)),
    [draft.template_id],
  )
  const overrideSet = useMemo(
    () => new Set(draft.steward_override_field_ids),
    [draft.steward_override_field_ids],
  )
  const missingSet = useMemo(
    () => new Set(validation.missingRequiredFieldIds),
    [validation.missingRequiredFieldIds],
  )

  return (
    <section
      className={styles.section}
      aria-labelledby={headingId}
      aria-label="Temporary grievance draft"
    >
      <p className={styles.tempBanner} role="status">
        Unsaved grievance draft — Cancel discards this draft. Save creates an
        official grievance artifact.
      </p>

      <header className={styles.reportHeader}>
        <h3 id={headingId} className={styles.sectionHeading}>
          {templateDisplayName(draft.template_id)}
        </h3>
        <div className={styles.metaRow}>
          <span className={styles.tempBadge}>Temporary</span>
          {dirty ? <span className={styles.dirtyBadge}>Edited</span> : null}
          <span className={styles.versionMeta}>
            Template: {draft.template_id}
          </span>
          <span className={styles.versionMeta}>
            Workflow: {stepTypeLabel(draft.step_type)}
          </span>
          <span className={styles.versionMeta}>
            Draft status: {draft.draft_status ?? '—'}
          </span>
        </div>
      </header>

      <GrievanceSaveActions
        busy={busy}
        busyMode={busyMode}
        dirty={dirty}
        onSave={onSave}
        onSaveAndPrint={onSaveAndPrint}
        onCancel={onCancel}
        onValidate={onValidate}
      />

      <DraftValidationSummary
        validation={validation}
        serverDraftStatus={draft.draft_status}
        showInvalidFocusHint={highlightInvalid}
      />

      <div className={styles.formSections}>
        {sections.map((group) => (
          <section
            key={group.section}
            className={styles.formSection}
            aria-label={group.section}
          >
            <h4 className={styles.blockHeading}>{group.section}</h4>
            <div className={styles.fieldGrid}>
              {group.fields.map((field) => {
                const value = draft.field_values[field.id] ?? ''
                const edited = overrideSet.has(field.id)
                const invalid =
                  highlightInvalid && missingSet.has(field.id)
                const inputId = `grievance-field-${field.id}`
                const hintId = `${inputId}-hint`
                const warnId = `${inputId}-warn`
                const describedBy = [
                  hintId,
                  field.protected && !value.trim() ? warnId : null,
                ]
                  .filter(Boolean)
                  .join(' ')

                return (
                  <div
                    key={field.id}
                    className={`${styles.field}${field.multiline ? ` ${styles.fieldFull}` : ''}`}
                  >
                    <label className={styles.fieldLabel} htmlFor={inputId}>
                      {field.label}
                      {field.required ? (
                        <span className={styles.requiredMark} title="Required">
                          {' '}
                          *
                        </span>
                      ) : null}
                    </label>
                    {field.multiline ? (
                      <textarea
                        id={inputId}
                        className={`${styles.fieldTextarea}${invalid ? ` ${styles.fieldInvalid}` : ''}`}
                        value={value}
                        disabled={busy}
                        required={field.required}
                        aria-required={field.required}
                        aria-invalid={invalid || undefined}
                        aria-describedby={describedBy || undefined}
                        onChange={(event) =>
                          onChangeField(field.id, event.target.value)
                        }
                      />
                    ) : (
                      <input
                        id={inputId}
                        className={`${styles.fieldInput}${invalid ? ` ${styles.fieldInvalid}` : ''}`}
                        type="text"
                        value={value}
                        disabled={busy}
                        required={field.required}
                        aria-required={field.required}
                        aria-invalid={invalid || undefined}
                        aria-describedby={describedBy || undefined}
                        onChange={(event) =>
                          onChangeField(field.id, event.target.value)
                        }
                      />
                    )}
                    <p id={hintId} className={styles.fieldHint}>
                      {edited ? (
                        <span className={styles.fieldEdited}>
                          Steward override
                        </span>
                      ) : value.trim() ? (
                        <span>Generated draft value</span>
                      ) : (
                        <span>Blank — not invented</span>
                      )}
                    </p>
                    {field.protected && !value.trim() ? (
                      <p
                        id={warnId}
                        className={`${styles.fieldHint} ${styles.fieldProtected}`}
                      >
                        Protected field — leave blank unless you have the
                        verified fact. Generation will not invent this value.
                      </p>
                    ) : null}
                  </div>
                )
              })}
            </div>
          </section>
        ))}
      </div>
    </section>
  )
}
