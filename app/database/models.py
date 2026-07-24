from datetime import datetime
from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, Boolean, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.session import Base
from pgvector.sqlalchemy import Vector


class Organization(Base):
    __tablename__ = "organizations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    union_type: Mapped[str] = mapped_column(String(100), nullable=False)
    local_number: Mapped[str | None] = mapped_column(String(100), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    source_documents: Mapped[list["SourceDocument"]] = relationship(back_populates="organization")


class SourceDocument(Base):
    __tablename__ = "source_documents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    organization_id: Mapped[int | None] = mapped_column(ForeignKey("organizations.id"), nullable=True)

    source_id: Mapped[str] = mapped_column(String(150), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    source_type: Mapped[str] = mapped_column(String(100), nullable=False)

    official_page: Mapped[str | None] = mapped_column(Text, nullable=True)
    download_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    final_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    local_path: Mapped[str | None] = mapped_column(Text, nullable=True)

    sha256: Mapped[str | None] = mapped_column(String(128), nullable=True)
    content_type: Mapped[str | None] = mapped_column(String(100), nullable=True)

    # W5 knowledge-foundation metadata. These fields make source processing
    # versioned, observable, retryable, and corpus-aware.
    version: Mapped[str | None] = mapped_column(String(80), nullable=True)
    document_metadata: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    processing_strategy: Mapped[str | None] = mapped_column(
        String(80),
        nullable=True,
    )
    processing_status: Mapped[str] = mapped_column(
        String(40),
        nullable=False,
        default="pending",
        index=True,
    )
    processed_sha256: Mapped[str | None] = mapped_column(
        String(128),
        nullable=True,
    )
    processed_at: Mapped[datetime | None] = mapped_column(
        DateTime,
        nullable=True,
    )
    processing_error: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    is_current: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    organization: Mapped["Organization"] = relationship(back_populates="source_documents")
    chunks: Mapped[list["SourceChunk"]] = relationship(back_populates="source_document")


class SourceChunk(Base):
    __tablename__ = "source_chunks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    source_document_id: Mapped[int] = mapped_column(ForeignKey("source_documents.id"), nullable=False)

    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    page_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    section_label: Mapped[str | None] = mapped_column(String(100), nullable=True)
    text: Mapped[str] = mapped_column(Text, nullable=False)

    # Corpus-specific structure such as handbook code, chapter, section,
    # heading, and the chunking-strategy version used to create this chunk.
    chunk_metadata: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    embedding: Mapped[list[float] | None] = mapped_column(Vector(1536), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    source_document: Mapped["SourceDocument"] = relationship(back_populates="chunks")


class GrievanceCase(Base):
    """
    Saved grievance research session supporting follow-up questions,
    report versioning, and case reopen.
    """

    __tablename__ = "grievance_cases"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    case_uuid: Mapped[str] = mapped_column(String(36), unique=True, nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    user_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    local_number: Mapped[str | None] = mapped_column(String(100), nullable=True)
    initial_question: Mapped[str] = mapped_column(Text, nullable=False)
    known_facts: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    status: Mapped[str] = mapped_column(String(50), default="open")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )

    messages: Mapped[list["CaseMessage"]] = relationship(back_populates="case")
    report_versions: Mapped[list["CaseReportVersion"]] = relationship(
        back_populates="case"
    )
    case_steps: Mapped[list["CaseStep"]] = relationship(back_populates="case")
    timeline_events: Mapped[list["CaseTimelineEventRecord"]] = relationship(
        back_populates="case",
    )
    form_draft_records: Mapped[list["CaseFormDraftRecord"]] = relationship(
        back_populates="case",
    )
    saved_artifacts: Mapped[list["CaseSavedArtifact"]] = relationship(
        back_populates="case",
    )
    assets: Mapped[list["CaseAsset"]] = relationship(back_populates="case")
    case_memory: Mapped["CaseMemoryRecord | None"] = relationship(
        back_populates="case",
        uselist=False,
    )
    domain_events: Mapped[list["CaseDomainEvent"]] = relationship(
        back_populates="case",
    )


class CaseMemoryRecord(Base):
    """First-class durable Case Memory — permanent structured case understanding.

    Updated by meaningful interactions. Restored before AI continuity assembly.
    Not reconstructed solely from chat transcripts.
    """

    __tablename__ = "case_memories"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    case_id: Mapped[int] = mapped_column(
        ForeignKey("grievance_cases.id"),
        unique=True,
        nullable=False,
        index=True,
    )
    case_uuid: Mapped[str] = mapped_column(
        String(36),
        unique=True,
        nullable=False,
        index=True,
    )
    schema_version: Mapped[str] = mapped_column(
        String(40),
        nullable=False,
        default="case_memory_v1",
    )
    memory_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    workflow_state: Mapped[str | None] = mapped_column(String(80), nullable=True)
    reopen_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )

    case: Mapped["GrievanceCase"] = relationship(back_populates="case_memory")


class CaseDomainEvent(Base):
    """Internal case-domain event for event-driven Case Memory updates.

    Not a steward-facing Official Case Record substitute. Steward timeline
    events remain in case_timeline_events; this table drives memory/workflow
    projections with idempotent synchronous processing.
    """

    __tablename__ = "case_domain_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    event_id: Mapped[str] = mapped_column(
        String(36), unique=True, nullable=False, index=True
    )
    case_id: Mapped[int] = mapped_column(
        ForeignKey("grievance_cases.id"), nullable=False, index=True
    )
    case_uuid: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    event_type: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    occurred_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    actor_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    grievance_step: Mapped[str | None] = mapped_column(String(50), nullable=True)
    source_type: Mapped[str | None] = mapped_column(String(80), nullable=True)
    source_uuid: Mapped[str | None] = mapped_column(String(36), nullable=True)
    metadata_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    idempotency_key: Mapped[str | None] = mapped_column(String(160), nullable=True)
    schema_version: Mapped[str] = mapped_column(
        String(40), nullable=False, default="case_domain_event_v1"
    )
    processed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    processing_status: Mapped[str] = mapped_column(
        String(40), nullable=False, default="pending"
    )
    steward_timeline_event_uuid: Mapped[str | None] = mapped_column(
        String(36), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    case: Mapped["GrievanceCase"] = relationship(back_populates="domain_events")


class CaseMessage(Base):
    """Conversation history within a grievance case."""

    __tablename__ = "case_messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    case_id: Mapped[int] = mapped_column(ForeignKey("grievance_cases.id"), nullable=False)
    role: Mapped[str] = mapped_column(String(20), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    message_metadata: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    case: Mapped["GrievanceCase"] = relationship(back_populates="messages")


class CaseReportVersion(Base):
    """
    Versioned GrievanceHub Analysis Report stored as structured JSON.
    New follow-up analysis creates a new version; prior versions are preserved.
    """

    __tablename__ = "case_report_versions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    case_id: Mapped[int] = mapped_column(ForeignKey("grievance_cases.id"), nullable=False)
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    trigger_message_id: Mapped[int | None] = mapped_column(
        ForeignKey("case_messages.id"),
        nullable=True,
    )
    report_data: Mapped[dict] = mapped_column(JSON, nullable=False)
    ranked_authorities: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    issue_analysis: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    evidence_items: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    retrieval_gaps: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    source_coverage_audit: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    report_summary: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    case: Mapped["GrievanceCase"] = relationship(back_populates="report_versions")


class CaseStep(Base):
    """One grievance step/stage within a saved case workspace (Phase 1.4D)."""

    __tablename__ = "case_steps"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    case_id: Mapped[int] = mapped_column(ForeignKey("grievance_cases.id"), nullable=False)
    case_uuid: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    step_type: Mapped[str] = mapped_column(String(50), nullable=False)
    step_number: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="open")
    is_closed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    was_reopened: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    appealed_from_prior_step: Mapped[str | None] = mapped_column(String(50), nullable=True)
    prior_step_id: Mapped[int | None] = mapped_column(
        ForeignKey("case_steps.id"),
        nullable=True,
    )
    prior_step_outcome_uuid: Mapped[str | None] = mapped_column(String(36), nullable=True)
    report_version_id: Mapped[int | None] = mapped_column(
        ForeignKey("case_report_versions.id"),
        nullable=True,
    )
    report_version_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    follow_up_message_ids: Mapped[list | None] = mapped_column(JSON, nullable=True)
    template_id: Mapped[str | None] = mapped_column(String(150), nullable=True)
    template_available: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    template_availability: Mapped[str | None] = mapped_column(String(80), nullable=True)
    step_metadata: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    opened_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    reopened_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )

    case: Mapped["GrievanceCase"] = relationship(back_populates="case_steps")
    prior_step: Mapped["CaseStep | None"] = relationship(
        remote_side="CaseStep.id",
        foreign_keys=[prior_step_id],
    )
    outcomes: Mapped[list["CaseStepOutcome"]] = relationship(
        back_populates="case_step",
        foreign_keys="CaseStepOutcome.case_step_id",
    )
    timeline_events: Mapped[list["CaseTimelineEventRecord"]] = relationship(
        back_populates="case_step",
    )
    form_draft_records: Mapped[list["CaseFormDraftRecord"]] = relationship(
        back_populates="case_step",
    )


class CaseStepOutcome(Base):
    """Management decision/outcome for a grievance step (Phase 1.4D)."""

    __tablename__ = "case_step_outcomes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    outcome_uuid: Mapped[str] = mapped_column(String(36), unique=True, nullable=False, index=True)
    case_id: Mapped[int] = mapped_column(ForeignKey("grievance_cases.id"), nullable=False)
    case_uuid: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    case_step_id: Mapped[int] = mapped_column(ForeignKey("case_steps.id"), nullable=False)
    step_type: Mapped[str] = mapped_column(String(50), nullable=False)
    outcome_type: Mapped[str] = mapped_column(String(50), nullable=False, default="pending")
    decision_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    decision_date: Mapped[str | None] = mapped_column(String(50), nullable=True)
    decision_maker_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    decision_maker_title: Mapped[str | None] = mapped_column(String(255), nullable=True)
    decision_document_refs: Mapped[list | None] = mapped_column(JSON, nullable=True)
    steward_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    close_step: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    close_case: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    appeal_to_next_step: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    next_step_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    recorded_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    case_step: Mapped["CaseStep"] = relationship(
        back_populates="outcomes",
        foreign_keys=[case_step_id],
    )


class CaseTimelineEventRecord(Base):
    """Timestamped case workspace history event (Phase 1.4D)."""

    __tablename__ = "case_timeline_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    event_uuid: Mapped[str] = mapped_column(String(36), unique=True, nullable=False, index=True)
    case_id: Mapped[int] = mapped_column(ForeignKey("grievance_cases.id"), nullable=False)
    case_uuid: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    case_step_id: Mapped[int | None] = mapped_column(
        ForeignKey("case_steps.id"),
        nullable=True,
    )
    step_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    event_type: Mapped[str] = mapped_column(String(80), nullable=False)
    event_timestamp: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    details: Mapped[str | None] = mapped_column(Text, nullable=True)
    report_version_id: Mapped[int | None] = mapped_column(
        ForeignKey("case_report_versions.id"),
        nullable=True,
    )
    report_version_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    follow_up_message_ids: Mapped[list | None] = mapped_column(JSON, nullable=True)
    draft_record_id: Mapped[int | None] = mapped_column(
        ForeignKey("case_form_draft_records.id"),
        nullable=True,
    )
    draft_record_uuid: Mapped[str | None] = mapped_column(String(36), nullable=True)
    upload_refs: Mapped[list | None] = mapped_column(JSON, nullable=True)
    outcome_uuid: Mapped[str | None] = mapped_column(String(36), nullable=True)
    prior_step_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    next_step_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    export_ref: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    case: Mapped["GrievanceCase"] = relationship(back_populates="timeline_events")
    case_step: Mapped["CaseStep | None"] = relationship(back_populates="timeline_events")


class CaseFormDraftRecord(Base):
    """Editable working draft and official grievance form versions."""

    __tablename__ = "case_form_draft_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    draft_uuid: Mapped[str] = mapped_column(String(36), unique=True, nullable=False, index=True)
    case_id: Mapped[int] = mapped_column(ForeignKey("grievance_cases.id"), nullable=False)
    case_uuid: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    case_step_id: Mapped[int] = mapped_column(ForeignKey("case_steps.id"), nullable=False)
    template_id: Mapped[str] = mapped_column(String(150), nullable=False)
    template_version: Mapped[str | None] = mapped_column(String(80), nullable=True)
    report_version_id: Mapped[int | None] = mapped_column(
        ForeignKey("case_report_versions.id"),
        nullable=True,
    )
    report_version_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    follow_up_message_ids: Mapped[list | None] = mapped_column(JSON, nullable=True)
    draft_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    draft_status: Mapped[str] = mapped_column(String(50), nullable=False)
    validation_status: Mapped[str | None] = mapped_column(String(50), nullable=True)
    missing_required_field_ids: Mapped[list | None] = mapped_column(JSON, nullable=True)
    steward_override_field_ids: Mapped[list | None] = mapped_column(JSON, nullable=True)
    field_values: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    content_snapshot: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    is_official: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    saved_by: Mapped[str | None] = mapped_column(String(255), nullable=True)
    printed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    pdf_asset_uuid: Mapped[str | None] = mapped_column(String(36), nullable=True)
    idempotency_key: Mapped[str | None] = mapped_column(String(120), nullable=True)
    approval_status: Mapped[str | None] = mapped_column(String(50), nullable=True)
    export_status: Mapped[str | None] = mapped_column(String(50), nullable=True)
    export_attempted: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    exported_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)

    case: Mapped["GrievanceCase"] = relationship(back_populates="form_draft_records")
    case_step: Mapped["CaseStep"] = relationship(back_populates="form_draft_records")


class CaseSavedArtifact(Base):
    """Official Save-and-Print case artifact (immutable after save).

    Distinguishes steward-approved printed versions from auto-generated analysis
    drafts and editable working form drafts. Generic across future templates.
    """

    __tablename__ = "case_saved_artifacts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    artifact_uuid: Mapped[str] = mapped_column(
        String(36), unique=True, nullable=False, index=True
    )
    case_id: Mapped[int] = mapped_column(ForeignKey("grievance_cases.id"), nullable=False)
    case_uuid: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    artifact_type: Mapped[str] = mapped_column(String(50), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    version_label: Mapped[str] = mapped_column(String(255), nullable=False)
    grievance_step: Mapped[str | None] = mapped_column(String(50), nullable=True)
    template_id: Mapped[str | None] = mapped_column(String(150), nullable=True)
    template_version: Mapped[str | None] = mapped_column(String(80), nullable=True)
    content_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    key_summary_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    source_report_version_id: Mapped[int | None] = mapped_column(
        ForeignKey("case_report_versions.id"),
        nullable=True,
    )
    source_report_version_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    source_draft_record_uuid: Mapped[str | None] = mapped_column(String(36), nullable=True)
    pdf_asset_uuid: Mapped[str | None] = mapped_column(String(36), nullable=True)
    pdf_status: Mapped[str] = mapped_column(String(50), nullable=False, default="pending")
    printed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_latest_official: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    saved_by: Mapped[str | None] = mapped_column(String(255), nullable=True)
    saved_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    idempotency_key: Mapped[str | None] = mapped_column(String(120), nullable=True)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="official")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    case: Mapped["GrievanceCase"] = relationship(back_populates="saved_artifacts")


class CaseAsset(Base):
    """First-class case-owned artifact (Phase W3 Case Asset foundation).

    Uploaded documents are the only executable category in W3. Other categories
    (generated reports, grievances, exports, future attachments) share this
    table so later phases do not redesign the data model.
    """

    __tablename__ = "case_assets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    asset_uuid: Mapped[str] = mapped_column(
        String(36), unique=True, nullable=False, index=True
    )
    case_id: Mapped[int] = mapped_column(ForeignKey("grievance_cases.id"), nullable=False)
    case_uuid: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    asset_category: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    original_filename: Mapped[str | None] = mapped_column(String(255), nullable=True)
    stored_filename: Mapped[str | None] = mapped_column(String(255), nullable=True)
    stored_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    mime_type: Mapped[str | None] = mapped_column(String(150), nullable=True)
    file_size: Mapped[int | None] = mapped_column(Integer, nullable=True)
    sha256: Mapped[str | None] = mapped_column(String(128), nullable=True)
    uploaded_by: Mapped[str | None] = mapped_column(String(255), nullable=True)
    source: Mapped[str] = mapped_column(String(50), nullable=False, default="api")
    version_number: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    parent_asset_uuid: Mapped[str | None] = mapped_column(String(36), nullable=True)
    report_version_id: Mapped[int | None] = mapped_column(
        ForeignKey("case_report_versions.id"),
        nullable=True,
    )
    report_version_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    draft_record_uuid: Mapped[str | None] = mapped_column(String(36), nullable=True)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="active")
    asset_metadata: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )

    case: Mapped["GrievanceCase"] = relationship(back_populates="assets")