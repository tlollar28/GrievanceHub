import { vi } from 'vitest'
import type {
  OpenCaseResponse,
  ReopenCaseResponse,
  SavedCaseListResponse,
  SavedCaseSummary,
} from '../api/types/savedCases'
import type { CaseWorkspace } from '../api/types/workspace'
import type {
  CaseDetail,
  CreateCaseResponse,
  UpdateFactsResponse,
} from '../api/types/cases'
import type {
  CaseInteractionResponse,
  InteractionCitation,
  RetrievalStatus,
} from '../api/types/interactions'
import type {
  CaseMessage,
  ListCaseMessagesResponse,
} from '../api/types/messages'
import { MESSAGES_DEFAULT_LIMIT } from '../api/types/messages'
import type {
  CaseAssetListResponse,
  CaseAssetMetadata,
  CaseAssetUploadResponse,
} from '../api/types/assets'
import type {
  AnalysisPreviewPayload,
  AnalysisVersionDetail,
  AnalysisVersionListResponse,
  AnalysisVersionSummary,
  GenerateAnalysisResponse,
  GrievanceHubReportData,
  SaveAndPrintResponse,
} from '../api/types/reports'
import type {
  ArtifactCompareResponse,
  CaseHistoryContextResponse,
  CaseHistoryItem,
  CaseHistoryResponse,
  CaseTimelineEvent,
  SavedCaseTimelineResponse,
} from '../api/types/artifacts'
import type {
  CaseSavedArtifactDetail,
  CaseSavedArtifactListResponse,
  CaseSavedArtifactSummary,
  GenerateGrievanceResponse,
  GrievanceGenerationResult,
} from '../api/types/grievances'

export const SAMPLE_ASSET_UUID = 'aaaaaaaa-bbbb-4ccc-8ddd-eeeeeeeeeeee'
export const OTHER_ASSET_UUID = 'ffffffff-1111-4222-8333-444444444444'

export const SAMPLE_CASE_UUID = '11111111-1111-4111-8111-111111111111'
export const CLOSED_CASE_UUID = '22222222-2222-4222-8222-222222222222'
export const OTHER_CASE_UUID = '33333333-3333-4333-8333-333333333333'

export function makeSummary(
  overrides: Partial<SavedCaseSummary> = {},
): SavedCaseSummary {
  return {
    case_id: 501,
    case_uuid: SAMPLE_CASE_UUID,
    case_number: '501',
    title: 'Overtime dispute',
    issue_summary: 'Denied overtime for tour 2',
    grievant_or_class: 'Carrier A',
    current_step_type: 'step_1_initial',
    current_step_status: 'open',
    workspace_status: 'open',
    legacy_case_status: 'open',
    created_at: '2026-07-01T12:00:00Z',
    last_activity_at: '2026-07-20T15:30:00Z',
    closed_at: null,
    reopened_at: null,
    latest_outcome_summary: null,
    latest_outcome_type: null,
    template_availability: null,
    available_actions: ['open_case', 'view_timeline'],
    has_step_progression: true,
    ...overrides,
  }
}

export function makeListResponse(
  cases: SavedCaseSummary[],
  overrides: Partial<SavedCaseListResponse> = {},
): SavedCaseListResponse {
  return {
    count: cases.length,
    total: cases.length,
    limit: 25,
    offset: 0,
    has_more: false,
    order: 'newest_first',
    status_filter: 'all',
    step_filter: null,
    search: null,
    cases,
    payload_mode: 'summary_only',
    ...overrides,
  }
}

/** Full GET /cases/{uuid}/workspace shape used by M2 shell. */
export function makeWorkspace(
  overrides: Partial<CaseWorkspace> = {},
): CaseWorkspace {
  const caseUuid = overrides.case_uuid ?? SAMPLE_CASE_UUID
  const title = overrides.title ?? 'Overtime dispute'
  return {
    case_uuid: caseUuid,
    title,
    user_name: 'Steward Ada',
    local_number: '501',
    initial_question: 'Denied overtime for tour 2',
    known_facts: {
      tour: '2',
      location: 'Station A',
    },
    status: 'open',
    created_at: '2026-07-01T12:00:00Z',
    updated_at: '2026-07-20T15:30:00Z',
    messages: [],
    message_count: 3,
    conversation_history: {
      embedded_in_workspace: false,
      total: 3,
      retrieval: {
        method: 'GET',
        path: `/cases/${caseUuid}/messages`,
        default_limit: 50,
        max_limit: 100,
      },
    },
    workspace_summary: {
      case_uuid: caseUuid,
      title,
      status: 'open',
      workspace_status: 'open',
      current_step_type: 'step_1_initial',
      message_count: 3,
      asset_count: 1,
      has_step_progression: true,
    },
    case_overview: {
      case_uuid: caseUuid,
      case_number: '501',
      employee: 'Carrier A',
      issue: 'Denied overtime for tour 2',
      current_status: 'open',
      current_step: 'step_1_initial',
      explicit_workflow_state: 'case_open',
      current_recommendation: null,
      open_questions: ['Was overtime properly posted?'],
      outstanding_issues: [],
      evidence_count: 0,
      analysis_report_count: 0,
      official_grievance_count: 0,
      management_response_count: 0,
      last_activity_at: '2026-07-20T15:30:00Z',
      assigned_steward: 'Steward Ada',
      reopen_count: 0,
      source: 'case_memory',
    },
    case_memory: {
      schema_version: 'case_memory_v1',
      case_is_system_of_record: true,
      restored_from: 'case_memory',
      facts: {
        tour: '2',
        location: 'Station A',
      },
      status: 'open',
      current_grievance_step: 'step_1_initial',
      workflow: { explicit_state: 'case_open' },
      open_questions: ['Was overtime properly posted?'],
      outstanding_issues: [],
      current_recommendation: null,
      full_transcript_embedded: false,
      full_artifact_bodies_embedded: false,
      reopen_count: 0,
    },
    timeline: [
      {
        event_type: 'case_created',
        title: 'Case created',
        step_type: 'step_1_initial',
        event_timestamp: '2026-07-01T12:00:00Z',
      },
      {
        event_type: 'case_opened',
        title: 'Step 1 opened',
        step_type: 'step_1_initial',
        event_timestamp: '2026-07-01T12:00:01Z',
      },
    ],
    timeline_total_count: 2,
    step_progression: {
      has_step_progression: true,
      workspace_status: 'open',
      current_step_type: 'step_1_initial',
      steps: [
        {
          step_type: 'step_1_initial',
          status: 'open',
        },
      ],
      timeline: [],
    },
    uploaded_assets: [
      {
        asset_uuid: 'asset-1',
        original_filename: 'schedule.pdf',
        asset_category: 'uploaded_document',
      },
    ],
    assets: [
      {
        asset_uuid: 'asset-1',
        original_filename: 'schedule.pdf',
        asset_category: 'uploaded_document',
      },
    ],
    official_artifacts: [],
    case_memory_restored_first: true,
    ai_context_restored: true,
    restore_action_required: false,
    ...overrides,
  }
}

export function makeCaseDetail(
  overrides: Partial<CaseDetail> = {},
): CaseDetail {
  return {
    case_uuid: SAMPLE_CASE_UUID,
    title: 'Overtime dispute',
    user_name: 'Steward Ada',
    local_number: '501',
    initial_question: 'Denied overtime for tour 2',
    known_facts: { tour: '2' },
    status: 'open',
    created_at: '2026-07-01T12:00:00Z',
    updated_at: '2026-07-01T12:00:00Z',
    latest_report_version: null,
    report_summary: null,
    retrieval_gaps_summary: null,
    messages: [],
    latest_report: null,
    report_versions: [],
    ...overrides,
  }
}

export function makeCreateResponse(
  overrides: Partial<CreateCaseResponse> = {},
): CreateCaseResponse {
  return {
    case: makeCaseDetail(overrides.case),
    report_version: null,
  }
}

export function makeFactsResponse(
  overrides: Partial<UpdateFactsResponse> = {},
): UpdateFactsResponse {
  return {
    case_uuid: SAMPLE_CASE_UUID,
    title: 'Overtime dispute',
    user_name: 'Steward Ada',
    local_number: '501',
    initial_question: 'Denied overtime for tour 2',
    known_facts: { tour: '2', location: 'Station A' },
    status: 'open',
    created_at: '2026-07-01T12:00:00Z',
    updated_at: '2026-07-24T18:00:00Z',
    latest_report_version: null,
    report_summary: null,
    retrieval_gaps_summary: null,
    ...overrides,
  }
}

export function makeOpenResponse(
  overrides: Partial<OpenCaseResponse> = {},
): OpenCaseResponse {
  const summary = overrides.case ?? makeSummary()
  return {
    case: summary,
    action_taken: 'already_open',
    message: 'Case is open and ready (source=manual_ui).',
    workspace: makeWorkspace({ case_uuid: summary.case_uuid }),
    ...overrides,
  }
}

export function makeReopenResponse(
  overrides: Partial<ReopenCaseResponse> = {},
): ReopenCaseResponse {
  const summary =
    overrides.case ??
    makeSummary({
      case_uuid: CLOSED_CASE_UUID,
      workspace_status: 'reopened',
      available_actions: ['open_case', 'view_timeline'],
    })
  return {
    case: summary,
    action_taken: 'reopened',
    message: 'Case reopened on the same case workspace; Case Memory restored.',
    source: 'manual_ui',
    workspace: makeWorkspace({
      case_uuid: summary.case_uuid,
      title: summary.title,
      status: 'open',
      workspace_summary: {
        case_uuid: summary.case_uuid,
        title: summary.title,
        status: 'open',
        workspace_status: 'reopened',
        current_step_type: summary.current_step_type,
        message_count: 2,
        asset_count: 0,
      },
    }),
    ...overrides,
  }
}

export function makeCaseMessage(
  overrides: Partial<CaseMessage> = {},
): CaseMessage {
  return {
    id: 1,
    role: 'user',
    content: 'What does Article 10 say about overtime?',
    metadata: { intent: 'follow_up' },
    created_at: '2026-07-20T15:00:00Z',
    ...overrides,
  }
}

export function makeMessagesResponse(
  messages: CaseMessage[] = [],
  overrides: Partial<ListCaseMessagesResponse> = {},
): ListCaseMessagesResponse {
  const caseUuid = overrides.case_uuid ?? SAMPLE_CASE_UUID
  return {
    case_uuid: caseUuid,
    count: messages.length,
    total: messages.length,
    limit: MESSAGES_DEFAULT_LIMIT,
    offset: 0,
    order: 'oldest_first',
    has_more: false,
    messages,
    ...overrides,
  }
}

export function makeCitation(
  overrides: Partial<InteractionCitation> = {},
): InteractionCitation {
  return {
    document_type: 'CBA',
    document_name: 'Local 300 Agreement',
    article_or_section: 'Article 10',
    page: 12,
    quote: 'Overtime shall be offered by seniority.',
    grounded: true,
    grounding_provenance: 'retrieved_passage',
    ...overrides,
  }
}

export function makeInteractionResponse(
  overrides: Partial<CaseInteractionResponse> = {},
): CaseInteractionResponse {
  const citations = overrides.citations ?? [makeCitation()]
  const retrievalStatus: RetrievalStatus =
    overrides.retrieval_status === undefined
      ? 'ok'
      : (overrides.retrieval_status ?? 'ok')
  return {
    case_uuid: SAMPLE_CASE_UUID,
    status: 'completed',
    message: 'Conversation saved. No analysis report was generated.',
    workspace_current: true,
    user_message: {
      id: 101,
      role: 'user',
      content: 'What does Article 10 say about overtime?',
      metadata: { intent: 'case_interaction' },
      created_at: '2026-07-24T20:00:00Z',
    },
    assistant_message: {
      id: 102,
      role: 'assistant',
      content: 'Article 10 addresses overtime distribution by seniority.',
      metadata: {
        intent: 'follow_up',
        answer_type: 'argument',
        citations,
        disclosures: [],
        facts_needed: [],
      },
      created_at: '2026-07-24T20:00:01Z',
    },
    ai_answer: 'Article 10 addresses overtime distribution by seniority.',
    answer_type: 'argument',
    citations,
    disclosures: [],
    facts_needed: [],
    retrieval_status: retrievalStatus,
    retrieval_error: false,
    case_memory_update_status: 'not_applicable',
    analysis_versions_created: 0,
    grievance_draft_created: false,
    timeline_events: [],
    available_actions: [],
    ...overrides,
  }
}

export function makeAsset(
  overrides: Partial<CaseAssetMetadata> = {},
): CaseAssetMetadata {
  const caseUuid = overrides.case_uuid ?? SAMPLE_CASE_UUID
  const assetUuid = overrides.asset_uuid ?? SAMPLE_ASSET_UUID
  return {
    asset_uuid: assetUuid,
    case_uuid: caseUuid,
    asset_category: 'uploaded_document',
    original_filename: 'evidence-note.txt',
    stored_filename: `${assetUuid}_evidence-note.txt`,
    stored_path: `data/case_assets/${caseUuid}/${assetUuid}_evidence-note.txt`,
    mime_type: 'text/plain',
    file_size: 42,
    sha256: 'a'.repeat(64),
    uploaded_by: 'Steward Ada',
    source: 'manual_ui',
    version_number: 1,
    status: 'active',
    created_at: '2026-07-24T18:00:00Z',
    updated_at: '2026-07-24T18:00:00Z',
    ...overrides,
  }
}

export function makeAssetListResponse(
  assets: CaseAssetMetadata[] = [],
  overrides: Partial<CaseAssetListResponse> = {},
): CaseAssetListResponse {
  const caseUuid = overrides.case_uuid ?? SAMPLE_CASE_UUID
  return {
    case_uuid: caseUuid,
    count: assets.length,
    assets,
    ...overrides,
  }
}

export function makeUploadResponse(
  asset: CaseAssetMetadata = makeAsset(),
  overrides: Partial<CaseAssetUploadResponse> = {},
): CaseAssetUploadResponse {
  return {
    case_uuid: asset.case_uuid,
    asset,
    message: 'Case asset uploaded successfully.',
    ...overrides,
  }
}

export function makeReportData(
  overrides: Partial<GrievanceHubReportData> = {},
): GrievanceHubReportData {
  return {
    report_title: 'W6 M5 analysis smoke report',
    brand: 'GrievanceHub',
    generated_at: '2026-07-24T20:00:00Z',
    case_information: {
      case_id: SAMPLE_CASE_UUID,
      case_title: 'Overtime dispute',
      user_name: 'Steward Ada',
      local_number: '501',
    },
    research_draft_notice: 'Research draft — not an official filing.',
    your_question: 'Was overtime properly paid?',
    quick_assessment: {
      summary: 'Possible overtime violation based on supplied facts.',
      grievability: 'Potentially grievable',
      confidence: 'Medium',
      why: 'Contract overtime language may apply.',
    },
    secondary_issues: ['Schedule notice'],
    key_contract_violations: [
      {
        article_or_section: 'Article 8',
        issue: 'Overtime assignment',
        role: 'union_supporting',
        role_title: 'Union Supporting Authority',
        why_relevant: 'Addresses overtime distribution.',
        direct_quote: 'Overtime shall be distributed equitably.',
        citation: {
          document_name: 'National Agreement',
          document_type: 'CONTRACT',
          page: 12,
        },
      },
    ],
    recommended_remedy: {
      statements: ['Request make-whole overtime pay.'],
      grounding_authorities: ['Article 8'],
    },
    detailed_analysis: {
      grievance_framework: 'Evaluate overtime distribution under Article 8.',
      evidence_to_gather: ['Clock rings for the week'],
      strategic_tips: [
        { title: 'Documentation', text: 'Collect tour schedules.' },
      ],
    },
    supporting_evidence: [
      {
        document_name: 'National Agreement',
        document_type: 'CONTRACT',
        article_or_section: 'Article 8',
        page: 12,
        direct_quote: 'Overtime shall be distributed equitably.',
        what_it_supports: 'Equitable overtime distribution duty.',
      },
    ],
    union_supporting_authority: [],
    procedural_requirements: [],
    information_rights: [],
    timeline_requirements: [],
    remedy_authority: [],
    management_limiting_authority: [],
    background_authority: [],
    limitations: {
      missing_facts: ['Exact hours denied'],
      caveats: ['Authority corpus may be incomplete for local practice.'],
      known_facts: ['Tour 2'],
      retrieval_gaps: { local_mou: 'not_indexed' },
    },
    source_references: {
      found: [
        {
          source_type: 'CONTRACT',
          document_names: ['National Agreement'],
          authority_count: 1,
        },
      ],
      not_found: [],
    },
    citation_validation: {
      status: 'Needs Review',
      evidence_items_checked: 1,
      direct_quotes_found: 1,
      notes: ['Verify quote against source page.'],
    },
    ...overrides,
  }
}

export function makeAnalysisPreview(
  overrides: Partial<AnalysisPreviewPayload> = {},
): AnalysisPreviewPayload {
  const report = overrides.report_data ?? makeReportData()
  return {
    temporary: true,
    persisted: false,
    review_mode: 'read_only',
    editable: false,
    suggested_version_number_if_saved: 1,
    report_data: report,
    ranked_authorities: [],
    issue_analysis: null,
    evidence_items: report.supporting_evidence ?? [],
    retrieval_gaps: report.limitations?.retrieval_gaps ?? {},
    source_coverage_audit: null,
    report_summary: { title: report.report_title },
    ...overrides,
  }
}

export function makeGenerateResponse(
  overrides: Partial<GenerateAnalysisResponse> = {},
): GenerateAnalysisResponse {
  const preview = (overrides.preview ??
    overrides.analysis_preview ??
    makeAnalysisPreview()) as AnalysisPreviewPayload
  return {
    case_uuid: SAMPLE_CASE_UUID,
    action: 'generate_analysis_report',
    status: 'completed',
    message:
      'Temporary analysis preview ready for read-only review. Save creates the next Analysis Report version and artifact.',
    review_mode: 'read_only',
    editable: false,
    persisted: false,
    report_version: null,
    preview,
    analysis_preview: preview,
    analysis_preview_ready: true,
    analysis_editable: false,
    official_artifact_created: false,
    ...overrides,
  }
}

export function makeVersionSummary(
  overrides: Partial<AnalysisVersionSummary> = {},
): AnalysisVersionSummary {
  return {
    id: overrides.id ?? 1,
    version_number: overrides.version_number ?? 1,
    trigger_message_id: null,
    created_at: '2026-07-24T21:00:00Z',
    retrieval_gaps: null,
    source_coverage_audit: null,
    report_summary: { title: 'W6 M5 analysis smoke report' },
    ...overrides,
  }
}

export function makeVersionListResponse(
  versions: AnalysisVersionSummary[] = [],
  overrides: Partial<AnalysisVersionListResponse> = {},
): AnalysisVersionListResponse {
  const caseUuid = overrides.case_uuid ?? SAMPLE_CASE_UUID
  return {
    case_uuid: caseUuid,
    count: versions.length,
    versions,
    ...overrides,
  }
}

export function makeVersionDetail(
  overrides: Partial<AnalysisVersionDetail> = {},
): AnalysisVersionDetail {
  const summary = makeVersionSummary(overrides)
  return {
    ...summary,
    report_data: overrides.report_data ?? makeReportData(),
    ranked_authorities: overrides.ranked_authorities ?? [],
    issue_analysis: overrides.issue_analysis ?? null,
    evidence_items: overrides.evidence_items ?? [],
    ...overrides,
  }
}

export function makeSaveResponse(
  overrides: Partial<SaveAndPrintResponse> = {},
): SaveAndPrintResponse {
  const versionNumber =
    overrides.artifact?.version_number ??
    overrides.artifact?.source_report_version_number ??
    1
  return {
    case_uuid: SAMPLE_CASE_UUID,
    status: 'saved',
    message: 'Official analysis report saved.',
    print_ready: false,
    pdf_error: null,
    export_path: null,
    artifact: {
      artifact_uuid: 'aaaaaaaa-bbbb-4ccc-8ddd-eeeeeeeeeeee',
      case_uuid: SAMPLE_CASE_UUID,
      artifact_type: 'analysis_report',
      title: 'Analysis Report v1',
      version_number: versionNumber,
      version_label: `v${versionNumber}`,
      printed: false,
      pdf_status: 'pending',
      pdf_asset_uuid: null,
      is_latest_official: true,
      saved_by: 'Steward Ada',
      saved_at: '2026-07-24T21:05:00Z',
      source_report_version_number: versionNumber,
      retrieval: {
        artifact: `/cases/${SAMPLE_CASE_UUID}/artifacts/aaaaaaaa-bbbb-4ccc-8ddd-eeeeeeeeeeee`,
      },
      ...overrides.artifact,
    },
    ...overrides,
  }
}

export const SAMPLE_GRIEVANCE_ARTIFACT_UUID =
  'cccccccc-dddd-4eee-8fff-000000000001'
export const SAMPLE_ANALYSIS_ARTIFACT_UUID =
  'aaaaaaaa-bbbb-4ccc-8ddd-eeeeeeee0001'
export const SAMPLE_ANALYSIS_ARTIFACT_UUID_V2 =
  'aaaaaaaa-bbbb-4ccc-8ddd-eeeeeeee0002'
export const SAMPLE_HISTORY_EVENT_ID = 'evt-official-saved-001'

export function makeStep1FieldValues(
  overrides: Record<string, string> = {},
): Record<string, string> {
  return {
    form_date: '',
    branch_grievance_number: '',
    steward_name: '',
    grievant_name: 'Carrier A',
    grievant_name_or_class: 'Carrier A',
    ssn_or_employee_id: '',
    job_classification: 'Mail Handler',
    grievant_phone: '',
    home_address: '',
    city: '',
    state: '',
    zip: '',
    craft_seniority_date: '',
    service_seniority_date: '',
    duty_hours: '',
    installation_name: 'Station A',
    installation_station_branch: 'Station A',
    installation_city: '',
    installation_state: '',
    installation_zip: '',
    veteran_status: '',
    off_days: '',
    employment_status: '',
    employee_level: '',
    employee_step: '',
    violation_national: 'Article 8',
    violation_articles_citations: 'Article 8.5',
    violation_local_mou: '',
    violation_other_grounds: '',
    facts_dates: '',
    facts_time: '',
    facts_location: '',
    facts_what_happened: 'Denied overtime for tour 2.',
    corrective_action_requested: 'Pay overtime as required.',
    additional_sheet_attached: '',
    facts_continued: '',
    ...overrides,
  }
}

export function makeStep2FieldValues(
  overrides: Record<string, string> = {},
): Record<string, string> {
  return {
    form_date: '',
    branch_grievance_number: '',
    usps_number: '',
    installation_name: 'Station A',
    installation_station_branch: 'Station A',
    local_branch_number: '501',
    installation_phone_office: '',
    grievant_name: 'Carrier A',
    grievant_name_or_class: 'Carrier A',
    ssn_or_employee_id: '',
    job_classification: 'Mail Handler',
    grievant_phone: '',
    home_address: '',
    city: '',
    state: '',
    zip: '',
    craft_seniority_date: '',
    service_seniority_date: '',
    duty_hours: '',
    veteran_status: '',
    off_days: '',
    employment_status: '',
    step1_meeting_datetime: '',
    step1_usps_representative: '',
    step1_grievant_or_steward: '',
    step1_decision_by_name_title: '',
    step1_decision_outcome: '',
    step2_designee_name_title: '',
    step2_union_rep: 'Steward Ada',
    union_business_address: '',
    union_rep_phone_office: '',
    union_rep_phone_other: '',
    violation_national: 'Article 8',
    violation_articles_citations: 'Article 8.5',
    violation_local_mou: '',
    violation_other_grounds: '',
    facts_what_happened: 'Denied overtime for tour 2.',
    facts_datetime_location: '',
    corrective_action_requested: 'Pay overtime as required.',
    additional_sheet_attached: '',
    employee_level: '',
    employee_step: '',
    ...overrides,
  }
}

export function makeGrievanceGeneration(
  overrides: Partial<GrievanceGenerationResult> = {},
): GrievanceGenerationResult {
  return {
    draft_created: true,
    editable: true,
    official_artifact_created: false,
    template_id: 'official_grievance_worksheet_step_1',
    step_type: 'step_1_initial',
    draft_status: 'pending_required_fields',
    field_values: makeStep1FieldValues(),
    message: 'Temporary editable draft only — not persisted until Save.',
    ...overrides,
  }
}

export function makeGenerateGrievanceResponse(
  overrides: Partial<GenerateGrievanceResponse> = {},
): GenerateGrievanceResponse {
  const generation =
    overrides.grievance_generation === null
      ? null
      : makeGrievanceGeneration(
          (overrides.grievance_generation as
            | Partial<GrievanceGenerationResult>
            | undefined) ?? {},
        )
  return {
    case_uuid: SAMPLE_CASE_UUID,
    action: 'generate_grievance',
    status: 'completed',
    message:
      'Temporary editable grievance draft ready for review. Save creates the first grievance artifact/version.',
    steward_action_label: 'Generate Grievance',
    grievance_draft_created: true,
    official_artifact_created: false,
    grievance_generation: generation,
    ...overrides,
  }
}

export function makeGrievanceArtifactSummary(
  overrides: Partial<CaseSavedArtifactSummary> = {},
): CaseSavedArtifactSummary {
  return {
    artifact_uuid: SAMPLE_GRIEVANCE_ARTIFACT_UUID,
    case_uuid: SAMPLE_CASE_UUID,
    artifact_type: 'grievance_form',
    title: 'Official Grievance Worksheet — Step 1 v1',
    version_number: 1,
    version_label: 'v1',
    grievance_step: 'step_1_initial',
    template_id: 'official_grievance_worksheet_step_1',
    printed: false,
    pdf_status: 'ready',
    pdf_asset_uuid: null,
    is_latest_official: true,
    saved_by: 'Steward Ada',
    saved_at: '2026-07-24T22:00:00Z',
    ...overrides,
  }
}

export function makeGrievanceArtifactList(
  artifacts: CaseSavedArtifactSummary[] = [],
  overrides: Partial<CaseSavedArtifactListResponse> = {},
): CaseSavedArtifactListResponse {
  const caseUuid = overrides.case_uuid ?? SAMPLE_CASE_UUID
  return {
    case_uuid: caseUuid,
    count: artifacts.length,
    artifacts,
    groups: {
      grievances: artifacts,
      analysis_reports: [],
      ...overrides.groups,
    },
    ...overrides,
  }
}

export function makeGrievanceArtifactDetail(
  overrides: Partial<CaseSavedArtifactDetail> = {},
): CaseSavedArtifactDetail {
  const summary = makeGrievanceArtifactSummary(overrides)
  return {
    ...summary,
    content_json: overrides.content_json ?? {
      template_id: summary.template_id,
      field_values: makeStep1FieldValues(),
    },
    pdf_download_path:
      overrides.pdf_download_path ??
      `/cases/${summary.case_uuid}/artifacts/${summary.artifact_uuid}/pdf`,
    ...overrides,
  }
}

export function makeGrievanceSaveResponse(
  overrides: Partial<SaveAndPrintResponse> = {},
): SaveAndPrintResponse {
  const artifact = makeGrievanceArtifactSummary({
    ...overrides.artifact,
  })
  return {
    case_uuid: SAMPLE_CASE_UUID,
    status: 'saved',
    message: 'Official grievance form saved.',
    print_ready: artifact.pdf_status === 'ready',
    pdf_error: null,
    export_path: `/cases/${SAMPLE_CASE_UUID}/artifacts/${artifact.artifact_uuid}/pdf`,
    ...overrides,
    artifact,
  }
}

export function makeAnalysisArtifactSummary(
  overrides: Partial<CaseSavedArtifactSummary> = {},
): CaseSavedArtifactSummary {
  return {
    artifact_uuid: SAMPLE_ANALYSIS_ARTIFACT_UUID,
    case_uuid: SAMPLE_CASE_UUID,
    artifact_type: 'analysis_report',
    title: 'Analysis Report v1',
    version_number: 1,
    version_label: 'v1',
    grievance_step: 'step_1_initial',
    template_id: null,
    printed: true,
    pdf_status: 'ready',
    pdf_asset_uuid: 'pdf-asset-analysis-1',
    is_latest_official: true,
    saved_by: 'Steward Ada',
    saved_at: '2026-07-24T20:00:00Z',
    source_report_version_number: 1,
    key_summary: {
      primary_issue: 'Denied overtime',
      grievability: 'Likely grievable',
      confidence: 'medium',
    },
    ...overrides,
  }
}

export function makeArtifactListResponse(
  artifacts: CaseSavedArtifactSummary[] = [],
  overrides: Partial<CaseSavedArtifactListResponse> = {},
): CaseSavedArtifactListResponse {
  const caseUuid = overrides.case_uuid ?? SAMPLE_CASE_UUID
  return {
    case_uuid: caseUuid,
    count: artifacts.length,
    artifacts,
    groups: {
      analysis_reports: artifacts.filter(
        (item) => item.artifact_type === 'analysis_report',
      ),
      grievances: artifacts.filter(
        (item) => item.artifact_type === 'grievance_form',
      ),
      ...overrides.groups,
    },
    ...overrides,
  }
}

export function makeAnalysisArtifactDetail(
  overrides: Partial<CaseSavedArtifactDetail> = {},
): CaseSavedArtifactDetail {
  const summary = makeAnalysisArtifactSummary(overrides)
  return {
    ...summary,
    content_json: overrides.content_json ?? {
      report_data: {
        report: {
          quick_assessment: {
            summary: 'Denied overtime appears grievable under Article 8.',
            grievability: 'Likely grievable',
            confidence: 'medium',
          },
        },
      },
      // Intentionally present in fixtures — UI must never render this.
      stored_path: '/secret/storage/path/should-not-display.pdf',
    },
    pdf_download_path:
      overrides.pdf_download_path ??
      `/cases/${summary.case_uuid}/artifacts/${summary.artifact_uuid}/pdf`,
    ...overrides,
  }
}

export function makeHistoryItem(
  overrides: Partial<CaseHistoryItem> = {},
): CaseHistoryItem {
  return {
    event_id: SAMPLE_HISTORY_EVENT_ID,
    event_type: 'analysis_report_saved_and_printed',
    title: 'Analysis report saved and printed',
    details: 'Official analysis artifact created',
    event_timestamp: '2026-07-24T20:00:00Z',
    icon: 'printed',
    clickable: true,
    artifact_uuid: SAMPLE_ANALYSIS_ARTIFACT_UUID,
    artifact_type: 'analysis_report',
    report_version_number: 1,
    context_path: `/cases/${SAMPLE_CASE_UUID}/history/${SAMPLE_HISTORY_EVENT_ID}/context`,
    record_class: 'official_record',
    display_label: 'Official saved',
    ...overrides,
  }
}

export function makeHistoryResponse(
  events: CaseHistoryItem[] = [makeHistoryItem()],
  overrides: Partial<CaseHistoryResponse> = {},
): CaseHistoryResponse {
  return {
    case_uuid: SAMPLE_CASE_UUID,
    label: 'Official Case Record',
    count: events.length,
    order: 'newest_first',
    events,
    ...overrides,
  }
}

export function makeTimelineEvent(
  overrides: Partial<CaseTimelineEvent> = {},
): CaseTimelineEvent {
  return {
    event_id: 'timeline-evt-001',
    case_uuid: SAMPLE_CASE_UUID,
    step_type: 'step_1_initial',
    event_type: 'case_created',
    event_timestamp: '2026-07-01T12:00:00Z',
    title: 'Case created',
    details: 'Workspace opened',
    references: {},
    ...overrides,
  }
}

export function makeTimelineResponse(
  events: CaseTimelineEvent[] = [makeTimelineEvent()],
  overrides: Partial<SavedCaseTimelineResponse> = {},
): SavedCaseTimelineResponse {
  return {
    case_uuid: SAMPLE_CASE_UUID,
    order: 'newest_first',
    count: events.length,
    events,
    ...overrides,
  }
}

export function makeHistoryContextResponse(
  overrides: Partial<CaseHistoryContextResponse> = {},
): CaseHistoryContextResponse {
  return {
    case_uuid: SAMPLE_CASE_UUID,
    event_id: SAMPLE_HISTORY_EVENT_ID,
    event_details: {
      event_uuid: SAMPLE_HISTORY_EVENT_ID,
      event_type: 'analysis_report_saved_and_printed',
      title: 'Analysis report saved and printed',
      details: 'Official analysis artifact created',
      event_timestamp: '2026-07-24T20:00:00Z',
      step_type: 'step_1_initial',
    },
    related_artifact: {
      artifact_uuid: SAMPLE_ANALYSIS_ARTIFACT_UUID,
      artifact_type: 'analysis_report',
      title: 'Analysis Report v1',
      version_number: 1,
    },
    related_conversation: {
      message_ids: [1, 2],
      messages: [
        { id: 1, role: 'user', content: 'Can we grieve denied overtime?' },
        {
          id: 2,
          role: 'assistant',
          content: 'Article 8 may support a grievance.',
        },
      ],
      bounded: true,
      full_transcript_replayed: false,
      window_size: 2,
    },
    related_evidence: [],
    related_workflow_state: {
      step_type: 'step_1_initial',
      event_type: 'analysis_report_saved_and_printed',
      note: 'Historical workflow snapshot from event linkage; not a rollback.',
    },
    related_decisions: [],
    previous_event: {
      event_id: 'timeline-evt-001',
      title: 'Case created',
    },
    next_event: null,
    retrieval_references: {
      history_context: `/cases/${SAMPLE_CASE_UUID}/history/${SAMPLE_HISTORY_EVENT_ID}/context`,
    },
    record_class: 'official_record',
    mutates_current_memory: false,
    unavailable_fields: [],
    ...overrides,
  }
}

export function makeCompareResponse(
  overrides: Partial<ArtifactCompareResponse> = {},
): ArtifactCompareResponse {
  const left = makeAnalysisArtifactDetail()
  const right = makeAnalysisArtifactDetail({
    artifact_uuid: SAMPLE_ANALYSIS_ARTIFACT_UUID_V2,
    title: 'Analysis Report v2',
    version_number: 2,
    version_label: 'v2',
    saved_at: '2026-07-25T10:00:00Z',
    key_summary: {
      primary_issue: 'Denied overtime — revised',
      grievability: 'Likely grievable',
      confidence: 'high',
    },
  })
  return {
    case_uuid: SAMPLE_CASE_UUID,
    artifact_type: 'analysis_report',
    left,
    right,
    changed_summary_keys: ['primary_issue', 'confidence'],
    left_only_summary_keys: [],
    right_only_summary_keys: [],
    version_delta: 1,
    retrieval_note:
      'Both official versions were retrieved automatically from the case record.',
    ...overrides,
  }
}

export function binaryResponse(
  body: BlobPart,
  contentType: string,
  status = 200,
  extraHeaders: Record<string, string> = {},
): Response {
  const blob = body instanceof Blob ? body : new Blob([body], { type: contentType })
  return {
    ok: status >= 200 && status < 300,
    status,
    headers: new Headers({
      'content-type': contentType,
      'content-disposition': 'inline; filename="report.bin"',
      ...extraHeaders,
    }),
    blob: async () => blob,
    json: async () => {
      throw new Error('Not JSON')
    },
    text: async () => (typeof body === 'string' ? body : ''),
  } as unknown as Response
}

export function jsonResponse(body: unknown, status = 200): Response {
  return {
    ok: status >= 200 && status < 300,
    status,
    headers: new Headers({ 'content-type': 'application/json' }),
    json: async () => body,
    text: async () => JSON.stringify(body),
  } as Response
}

export function installApiMock(
  handler: (
    input: RequestInfo | URL,
    init?: RequestInit,
  ) => Response | Promise<Response>,
  options: {
    autoHealth?: boolean
    autoEmptyMessages?: boolean
    autoEmptyAssets?: boolean
    autoEmptyVersions?: boolean
    autoEmptyArtifacts?: boolean
  } = {},
) {
  const autoHealth = options.autoHealth !== false
  const autoEmptyMessages = options.autoEmptyMessages !== false
  const autoEmptyAssets = options.autoEmptyAssets !== false
  const autoEmptyVersions = options.autoEmptyVersions !== false
  const autoEmptyArtifacts = options.autoEmptyArtifacts === true
  const fetchMock = vi.fn(
    async (input: RequestInfo | URL, init?: RequestInit) => {
      const url =
        typeof input === 'string'
          ? input
          : input instanceof URL
            ? input.toString()
            : input.url
      if (autoHealth && url.includes('/health')) {
        return jsonResponse({ status: 'healthy', service: 'GrievanceHub' })
      }
      if (
        autoEmptyMessages &&
        url.includes('/messages') &&
        (!init?.method || init.method === 'GET')
      ) {
        const match = url.match(/\/cases\/([^/]+)\/messages/)
        const caseUuid = match?.[1] ?? SAMPLE_CASE_UUID
        return jsonResponse(makeMessagesResponse([], { case_uuid: caseUuid }))
      }
      if (
        autoEmptyAssets &&
        /\/cases\/[^/]+\/assets(?:\?|$)/.test(url) &&
        (!init?.method || init.method === 'GET')
      ) {
        const match = url.match(/\/cases\/([^/]+)\/assets/)
        const caseUuid = match?.[1] ?? SAMPLE_CASE_UUID
        return jsonResponse(makeAssetListResponse([], { case_uuid: caseUuid }))
      }
      if (
        autoEmptyVersions &&
        /\/cases\/[^/]+\/versions\/?$/.test(url.split('?')[0] ?? url) &&
        (!init?.method || init.method === 'GET')
      ) {
        const match = url.match(/\/cases\/([^/]+)\/versions/)
        const caseUuid = match?.[1] ?? SAMPLE_CASE_UUID
        return jsonResponse(makeVersionListResponse([], { case_uuid: caseUuid }))
      }
      if (
        autoEmptyArtifacts &&
        /\/cases\/[^/]+\/artifacts(?:\?|$)/.test(url) &&
        (!init?.method || init.method === 'GET')
      ) {
        const match = url.match(/\/cases\/([^/]+)\/artifacts/)
        const caseUuid = match?.[1] ?? SAMPLE_CASE_UUID
        return jsonResponse(
          makeGrievanceArtifactList([], { case_uuid: caseUuid }),
        )
      }
      return handler(input, init)
    },
  )
  vi.stubGlobal('fetch', fetchMock)
  return fetchMock
}
