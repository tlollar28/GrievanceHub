"""Canonical Case Asset contract (Phase W3).

Every durable artifact belonging to a GrievanceCase is a Case Asset — not only
uploads. Categories cover uploaded documents today and leave room for generated
reports, grievances, exports, and future attachments without redesigning the
data model.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

CaseAssetCategory = Literal[
    "uploaded_document",
    "generated_report",
    "generated_grievance",
    "future_export",
    "future_attachment",
]

CaseAssetStatus = Literal["active", "superseded", "archived"]

CaseAssetSource = Literal[
    "manual_ui",
    "api",
    "system",
    "update_analysis",
    "generate_grievance",
    "export",
]

EXECUTABLE_ASSET_CATEGORIES: frozenset[str] = frozenset({"uploaded_document"})

PLACEHOLDER_ASSET_CATEGORIES: frozenset[str] = frozenset(
    {
        "generated_report",
        "generated_grievance",
        "future_export",
        "future_attachment",
    }
)


class CaseAssetMetadata(BaseModel):
    """Public metadata for one case asset (no file body)."""

    asset_uuid: str
    case_uuid: str
    asset_category: CaseAssetCategory
    original_filename: str | None = None
    stored_filename: str | None = None
    stored_path: str | None = Field(
        default=None,
        description="Repo-relative or data-dir-relative storage path (local only).",
    )
    mime_type: str | None = None
    file_size: int | None = Field(default=None, ge=0)
    sha256: str | None = None
    uploaded_by: str | None = Field(
        default=None,
        description="Steward/user label when known.",
    )
    source: CaseAssetSource | str = "api"
    version_number: int = Field(default=1, ge=1)
    parent_asset_uuid: str | None = Field(
        default=None,
        description="Prior asset UUID when this row is a newer version.",
    )
    report_version_id: int | None = None
    report_version_number: int | None = None
    draft_record_uuid: str | None = None
    status: CaseAssetStatus = "active"
    asset_metadata: dict | None = Field(
        default=None,
        description="Extensible JSON for future category-specific fields.",
    )
    created_at: datetime | None = None
    updated_at: datetime | None = None


class CaseAssetListResponse(BaseModel):
    """List of assets attached to one case."""

    case_uuid: str
    count: int
    assets: list[CaseAssetMetadata] = Field(default_factory=list)


class CaseAssetUploadResponse(BaseModel):
    """Result of uploading an uploaded_document asset."""

    case_uuid: str
    asset: CaseAssetMetadata
    message: str = "Case asset uploaded successfully."


class CaseAssetCategoryInfo(BaseModel):
    """Describes a supported asset category and W3 execution status."""

    category: CaseAssetCategory
    executable_in_w3: bool
    description: str
