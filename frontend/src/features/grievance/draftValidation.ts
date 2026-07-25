import type { DraftStatus, TemporaryGrievanceDraft } from '../../api/types/grievances'
import {
  getTemplateFields,
  type TemplateFieldMeta,
} from './templateFields'

export type DraftValidationView = {
  /** Client-derived draft status (backend remains authoritative on save). */
  clientDraftStatus: DraftStatus
  readyFieldIds: string[]
  missingRequiredFieldIds: string[]
  protectedBlankFieldIds: string[]
  readyForStewardReview: boolean
  /** Backend does not block incomplete Save — always true when draft exists. */
  savePermitted: boolean
  saveAndPrintPermitted: boolean
  fields: readonly TemplateFieldMeta[]
}

function isBlank(value: string | undefined): boolean {
  return !value || !value.trim()
}

export function validateTemporaryDraft(
  draft: TemporaryGrievanceDraft,
): DraftValidationView {
  const fields = getTemplateFields(draft.template_id)
  const missingRequiredFieldIds: string[] = []
  const protectedBlankFieldIds: string[] = []
  const readyFieldIds: string[] = []

  for (const field of fields) {
    const value = draft.field_values[field.id] ?? ''
    const blank = isBlank(value)
    if (field.required && blank) {
      missingRequiredFieldIds.push(field.id)
    } else if (!blank) {
      readyFieldIds.push(field.id)
    }
    if (field.protected && blank) {
      protectedBlankFieldIds.push(field.id)
    }
  }

  const readyForStewardReview = missingRequiredFieldIds.length === 0
  const clientDraftStatus: DraftStatus = readyForStewardReview
    ? 'ready_for_steward_review'
    : 'pending_required_fields'

  return {
    clientDraftStatus,
    readyFieldIds,
    missingRequiredFieldIds,
    protectedBlankFieldIds,
    readyForStewardReview,
    // Verified: save-and-print stores client validation fields as provided
    // and does not reject incomplete drafts.
    savePermitted: true,
    saveAndPrintPermitted: true,
    fields,
  }
}

export function fieldLabel(
  fieldId: string,
  fields: readonly TemplateFieldMeta[],
): string {
  return fields.find((f) => f.id === fieldId)?.label ?? fieldId
}
