"""
Structured schema for GrievanceHub Analysis Report output.

The report is stored as JSON (CaseReportVersion.report_data) and rendered
to HTML/PDF by future frontend/export services. Headings remain consistent;
section contents are generated dynamically from the user's question, facts,
uploaded files, and retrieved authorities.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


REPORT_SECTIONS = [
    "report_title",
    "brand",
    "generated_at",
    "case_information",
    "research_draft_notice",
    "your_question",
    "quick_assessment",
    "secondary_issues",
    "key_contract_violations",
    "recommended_remedy",
    "detailed_analysis",
    "matching_grievance_templates",
    "matching_grievance_templates_notice",
    "supporting_evidence",
    "union_supporting_authority",
    "procedural_requirements",
    "information_rights",
    "timeline_requirements",
    "remedy_authority",
    "management_limiting_authority",
    "background_authority",
    "limitations",
    "source_references",
    "source_summary",
    "citation_validation",
]


class Provenance(BaseModel):
    """Trace where narrative or list content was derived."""

    generator: str = Field(
        description="Service or rule that produced the content, e.g. narrative_generator."
    )
    inputs: list[str] = Field(default_factory=list)
    authority_keys: list[str] = Field(default_factory=list)


class ReportCitation(BaseModel):
    document_name: str = ""
    document_type: str = ""
    page: int | None = None
    chunk: int | None = None


class AuthorityReportItem(BaseModel):
    article_or_section: str = "Unknown"
    issue: str = ""
    role: str = "background_only"
    role_title: str = "Background Authority"
    why_relevant: str = ""
    direct_quote: str = ""
    relevance_score: float | None = None
    keyword_overlap: float | None = None
    citation: ReportCitation = Field(default_factory=ReportCitation)
    provenance: Provenance | None = None


class EvidenceItem(BaseModel):
    article_or_section: str = ""
    document_name: str = ""
    document_type: str = ""
    page: int | None = None
    chunk: int | None = None
    direct_quote: str = ""
    what_it_supports: str = ""
    how_to_use: str = ""
    provenance: Provenance | None = None


class QuickAssessment(BaseModel):
    summary: str = ""
    grievability: str = "Not Enough Information"
    confidence: Literal["High", "Medium", "Low"] = "Low"
    why: str = ""
    cited_authorities: list[str] = Field(default_factory=list)
    provenance: Provenance | None = None


class RecommendedRemedy(BaseModel):
    statements: list[str] = Field(default_factory=list)
    grounding_authorities: list[str] = Field(default_factory=list)
    insufficient_notice: str | None = None
    provenance: Provenance | None = None


class StrategicTip(BaseModel):
    title: str = ""
    text: str = ""
    provenance: Provenance | None = None


class DetailedAnalysis(BaseModel):
    grievance_framework: str = ""
    evidence_to_gather: list[str] = Field(default_factory=list)
    strategic_tips: list[StrategicTip] = Field(default_factory=list)
    provenance: Provenance | None = None


class Limitations(BaseModel):
    missing_facts: list[str] = Field(default_factory=list)
    retrieval_gaps: dict[str, Any] = Field(default_factory=dict)
    known_facts: list[str] = Field(default_factory=list)
    caveats: list[str] = Field(default_factory=list)
    provenance: Provenance | None = None


class SourceReferenceFound(BaseModel):
    source_type: str
    document_names: list[str] = Field(default_factory=list)
    authority_count: int = 0


class SourceReferenceNotFound(BaseModel):
    source_type: str | None = None
    issue: str = ""
    reason: str = ""


class SourceReferences(BaseModel):
    found: list[SourceReferenceFound] = Field(default_factory=list)
    not_found: list[SourceReferenceNotFound] = Field(default_factory=list)
    provenance: Provenance | None = None


class CitationValidation(BaseModel):
    status: str = "Needs Review"
    evidence_items_checked: int = 0
    direct_quotes_found: int = 0
    notes: list[str] = Field(default_factory=list)


class CaseInformation(BaseModel):
    case_id: str | None = None
    case_title: str | None = None
    user_name: str | None = None
    local_number: str | None = None


class GrievanceHubReport(BaseModel):
    report_title: str
    brand: str
    generated_at: datetime | str
    case_information: CaseInformation = Field(default_factory=CaseInformation)
    research_draft_notice: str = ""
    your_question: str = ""
    quick_assessment: QuickAssessment = Field(default_factory=QuickAssessment)
    secondary_issues: list[str] = Field(default_factory=list)
    key_contract_violations: list[AuthorityReportItem] = Field(default_factory=list)
    recommended_remedy: RecommendedRemedy = Field(default_factory=RecommendedRemedy)
    detailed_analysis: DetailedAnalysis = Field(default_factory=DetailedAnalysis)
    matching_grievance_templates: list[Any] = Field(default_factory=list)
    matching_grievance_templates_notice: str = ""
    supporting_evidence: list[EvidenceItem] = Field(default_factory=list)
    union_supporting_authority: list[AuthorityReportItem] = Field(default_factory=list)
    procedural_requirements: list[AuthorityReportItem] = Field(default_factory=list)
    information_rights: list[AuthorityReportItem] = Field(default_factory=list)
    timeline_requirements: list[AuthorityReportItem] = Field(default_factory=list)
    remedy_authority: list[AuthorityReportItem] = Field(default_factory=list)
    management_limiting_authority: list[AuthorityReportItem] = Field(default_factory=list)
    background_authority: list[AuthorityReportItem] = Field(default_factory=list)
    limitations: Limitations = Field(default_factory=Limitations)
    source_references: SourceReferences = Field(default_factory=SourceReferences)
    source_summary: dict[str, Any] = Field(default_factory=dict)
    citation_validation: CitationValidation | None = None
    issue_analysis: dict[str, Any] | None = None

    model_config = {"extra": "allow"}
