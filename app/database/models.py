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
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    case: Mapped["GrievanceCase"] = relationship(back_populates="report_versions")