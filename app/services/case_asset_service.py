"""Case Asset service (Phase W3).

Owns persistence and local storage for case-owned artifacts. Uploaded documents
are executable in W3; other categories remain schema/model placeholders for
later phases (generated reports, grievances, exports, attachments).
"""

from __future__ import annotations

import hashlib
import re
from datetime import datetime
from pathlib import Path
from uuid import uuid4

from sqlalchemy.orm import Session

from app.config import CASE_ASSET_DIR, CASE_ASSET_MAX_UPLOAD_BYTES, PROJECT_ROOT
from app.database.models import CaseAsset, GrievanceCase
from app.schemas.case_asset_schema import (
    EXECUTABLE_ASSET_CATEGORIES,
    PLACEHOLDER_ASSET_CATEGORIES,
    CaseAssetCategory,
    CaseAssetCategoryInfo,
    CaseAssetListResponse,
    CaseAssetMetadata,
    CaseAssetSource,
    CaseAssetUploadResponse,
)
from app.services.case_service import CaseNotFoundError

_UNSAFE_FILENAME_RE = re.compile(r"[^\w.\- ()\[\]]+", re.UNICODE)
_MAX_FILENAME_LEN = 180


class CaseAssetError(Exception):
    """Base error for case asset operations."""


class CaseAssetNotFoundError(CaseAssetError):
    def __init__(self, asset_uuid: str) -> None:
        self.asset_uuid = asset_uuid
        super().__init__(f"Case asset not found: {asset_uuid}")


class CaseAssetValidationError(CaseAssetError):
    pass


class CaseAssetCategoryNotExecutableError(CaseAssetError):
    def __init__(self, category: str) -> None:
        self.category = category
        super().__init__(
            f"Asset category '{category}' is a W3 placeholder and cannot be "
            "uploaded yet. Only 'uploaded_document' is executable in Phase W3."
        )


class CaseAssetService:
    """Canonical boundary for case asset metadata and local file storage."""

    CATEGORY_DESCRIPTIONS: dict[str, str] = {
        "uploaded_document": "Steward-uploaded evidence or supporting files.",
        "generated_report": "Generated analysis report artifact (placeholder in W3).",
        "generated_grievance": "Generated grievance draft/form artifact (placeholder in W3).",
        "future_export": "Exported PDF/DOCX or similar (placeholder in W3).",
        "future_attachment": "Future arbitration/settlement/media attachment (placeholder in W3).",
    }

    def __init__(self, db: Session) -> None:
        self.db = db

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @classmethod
    def list_category_info(cls) -> list[CaseAssetCategoryInfo]:
        infos: list[CaseAssetCategoryInfo] = []
        for category, description in cls.CATEGORY_DESCRIPTIONS.items():
            infos.append(
                CaseAssetCategoryInfo(
                    category=category,  # type: ignore[arg-type]
                    executable_in_w3=category in EXECUTABLE_ASSET_CATEGORIES,
                    description=description,
                )
            )
        return infos

    def list_assets(
        self,
        case_uuid: str,
        *,
        category: CaseAssetCategory | None = None,
        include_non_active: bool = False,
    ) -> CaseAssetListResponse:
        self._require_case(case_uuid)
        query = self.db.query(CaseAsset).filter(CaseAsset.case_uuid == case_uuid)
        if category is not None:
            query = query.filter(CaseAsset.asset_category == category)
        if not include_non_active:
            query = query.filter(CaseAsset.status == "active")
        rows = query.order_by(CaseAsset.created_at.asc(), CaseAsset.id.asc()).all()
        assets = [self.to_metadata(row) for row in rows]
        return CaseAssetListResponse(
            case_uuid=case_uuid,
            count=len(assets),
            assets=assets,
        )

    def get_asset(self, case_uuid: str, asset_uuid: str) -> CaseAssetMetadata:
        self._require_case(case_uuid)
        row = (
            self.db.query(CaseAsset)
            .filter(
                CaseAsset.case_uuid == case_uuid,
                CaseAsset.asset_uuid == asset_uuid,
            )
            .first()
        )
        if row is None:
            raise CaseAssetNotFoundError(asset_uuid)
        return self.to_metadata(row)

    def get_asset_row(self, case_uuid: str, asset_uuid: str) -> CaseAsset:
        row = (
            self.db.query(CaseAsset)
            .filter(
                CaseAsset.case_uuid == case_uuid,
                CaseAsset.asset_uuid == asset_uuid,
            )
            .first()
        )
        if row is None:
            raise CaseAssetNotFoundError(asset_uuid)
        return row

    def upload_document(
        self,
        case_uuid: str,
        *,
        filename: str | None,
        content: bytes,
        mime_type: str | None = None,
        uploaded_by: str | None = None,
        source: CaseAssetSource | str = "api",
        asset_metadata: dict | None = None,
    ) -> CaseAssetUploadResponse:
        """Persist an uploaded_document asset (metadata + local file bytes)."""
        return self._store_uploaded_file(
            case_uuid,
            category="uploaded_document",
            filename=filename,
            content=content,
            mime_type=mime_type,
            uploaded_by=uploaded_by,
            source=source,
            asset_metadata=asset_metadata,
        )

    def create_asset(
        self,
        case_uuid: str,
        *,
        category: CaseAssetCategory,
        filename: str | None = None,
        content: bytes | None = None,
        mime_type: str | None = None,
        uploaded_by: str | None = None,
        source: CaseAssetSource | str = "api",
        asset_metadata: dict | None = None,
    ) -> CaseAssetUploadResponse:
        """Create an asset. Only uploaded_document accepts file bodies in W3."""
        if category in PLACEHOLDER_ASSET_CATEGORIES:
            raise CaseAssetCategoryNotExecutableError(category)
        if category != "uploaded_document":
            raise CaseAssetValidationError(f"Unsupported asset category: {category}")
        if content is None:
            raise CaseAssetValidationError("uploaded_document requires file content.")
        return self.upload_document(
            case_uuid,
            filename=filename,
            content=content,
            mime_type=mime_type,
            uploaded_by=uploaded_by,
            source=source,
            asset_metadata=asset_metadata,
        )

    def resolve_upload_refs_for_context(
        self,
        case_uuid: str,
        upload_refs: list[str] | None,
    ) -> list[dict]:
        """Resolve upload_refs (asset UUIDs or legacy refs) into context dicts."""
        if not upload_refs:
            return []
        resolved: list[dict] = []
        for ref in upload_refs:
            if not ref:
                continue
            row = (
                self.db.query(CaseAsset)
                .filter(
                    CaseAsset.case_uuid == case_uuid,
                    CaseAsset.asset_uuid == ref,
                )
                .first()
            )
            if row is not None:
                resolved.append(self.to_context_dict(row))
            else:
                resolved.append({"file_id": ref, "ref": ref, "asset_uuid": None})
        return resolved

    def assets_for_case_context(self, case_uuid: str) -> list[dict]:
        """Active uploaded_document assets as analysis/follow-up context dicts."""
        rows = (
            self.db.query(CaseAsset)
            .filter(
                CaseAsset.case_uuid == case_uuid,
                CaseAsset.asset_category == "uploaded_document",
                CaseAsset.status == "active",
            )
            .order_by(CaseAsset.created_at.asc(), CaseAsset.id.asc())
            .all()
        )
        return [self.to_context_dict(row) for row in rows]

    # ------------------------------------------------------------------
    # Serialization helpers
    # ------------------------------------------------------------------

    @staticmethod
    def to_metadata(row: CaseAsset) -> CaseAssetMetadata:
        return CaseAssetMetadata(
            asset_uuid=row.asset_uuid,
            case_uuid=row.case_uuid,
            asset_category=row.asset_category,  # type: ignore[arg-type]
            original_filename=row.original_filename,
            stored_filename=row.stored_filename,
            stored_path=row.stored_path,
            mime_type=row.mime_type,
            file_size=row.file_size,
            sha256=row.sha256,
            uploaded_by=row.uploaded_by,
            source=row.source,
            version_number=row.version_number or 1,
            parent_asset_uuid=row.parent_asset_uuid,
            report_version_id=row.report_version_id,
            report_version_number=row.report_version_number,
            draft_record_uuid=row.draft_record_uuid,
            status=row.status,  # type: ignore[arg-type]
            asset_metadata=row.asset_metadata,
            created_at=row.created_at,
            updated_at=row.updated_at,
        )

    @staticmethod
    def to_context_dict(row: CaseAsset) -> dict:
        """Shape compatible with CaseService uploaded_files context."""
        return {
            "asset_uuid": row.asset_uuid,
            "file_id": row.asset_uuid,
            "ref": row.asset_uuid,
            "filename": row.original_filename,
            "original_filename": row.original_filename,
            "stored_filename": row.stored_filename,
            "stored_path": row.stored_path,
            "mime_type": row.mime_type,
            "file_size": row.file_size,
            "sha256": row.sha256,
            "asset_category": row.asset_category,
            "source": row.source,
            "uploaded_by": row.uploaded_by,
            "version_number": row.version_number,
            "status": row.status,
        }

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _require_case(self, case_uuid: str) -> GrievanceCase:
        case = (
            self.db.query(GrievanceCase)
            .filter(GrievanceCase.case_uuid == case_uuid)
            .first()
        )
        if case is None:
            raise CaseNotFoundError(case_uuid)
        return case

    def _store_uploaded_file(
        self,
        case_uuid: str,
        *,
        category: CaseAssetCategory,
        filename: str | None,
        content: bytes,
        mime_type: str | None,
        uploaded_by: str | None,
        source: CaseAssetSource | str,
        asset_metadata: dict | None,
    ) -> CaseAssetUploadResponse:
        case = self._require_case(case_uuid)
        if not content:
            raise CaseAssetValidationError("Uploaded file is empty.")
        if len(content) > CASE_ASSET_MAX_UPLOAD_BYTES:
            raise CaseAssetValidationError(
                f"File exceeds maximum size of {CASE_ASSET_MAX_UPLOAD_BYTES} bytes."
            )

        asset_uuid = str(uuid4())
        safe_original = self._safe_filename(filename)
        stored_filename = f"{asset_uuid}_{safe_original}"
        case_dir = CASE_ASSET_DIR / case_uuid
        case_dir.mkdir(parents=True, exist_ok=True)
        absolute_path = (case_dir / stored_filename).resolve()
        self._assert_path_inside_asset_root(absolute_path)

        absolute_path.write_bytes(content)
        digest = hashlib.sha256(content).hexdigest()
        relative_path = self._relative_storage_path(absolute_path)

        now = datetime.utcnow()
        row = CaseAsset(
            asset_uuid=asset_uuid,
            case_id=case.id,
            case_uuid=case_uuid,
            asset_category=category,
            original_filename=safe_original,
            stored_filename=stored_filename,
            stored_path=relative_path,
            mime_type=mime_type,
            file_size=len(content),
            sha256=digest,
            uploaded_by=uploaded_by or case.user_name,
            source=source,
            version_number=1,
            status="active",
            asset_metadata=asset_metadata,
            created_at=now,
            updated_at=now,
        )
        self.db.add(row)
        case.updated_at = now
        self.db.commit()
        self.db.refresh(row)
        return CaseAssetUploadResponse(
            case_uuid=case_uuid,
            asset=self.to_metadata(row),
        )

    @staticmethod
    def _safe_filename(filename: str | None) -> str:
        raw = (filename or "upload.bin").strip().replace("\\", "/").split("/")[-1]
        if not raw or raw in {".", ".."}:
            raw = "upload.bin"
        cleaned = _UNSAFE_FILENAME_RE.sub("_", raw).strip(" ._")
        if not cleaned:
            cleaned = "upload.bin"
        if len(cleaned) > _MAX_FILENAME_LEN:
            stem = Path(cleaned).stem[: _MAX_FILENAME_LEN - 20]
            suffix = Path(cleaned).suffix[:20]
            cleaned = f"{stem}{suffix}"
        return cleaned

    @staticmethod
    def _assert_path_inside_asset_root(path: Path) -> None:
        root = CASE_ASSET_DIR.resolve()
        try:
            path.resolve().relative_to(root)
        except ValueError as exc:
            raise CaseAssetValidationError(
                "Refusing to store asset outside CASE_ASSET_DIR."
            ) from exc

    @staticmethod
    def _relative_storage_path(absolute_path: Path) -> str:
        try:
            return str(absolute_path.resolve().relative_to(PROJECT_ROOT.resolve()))
        except ValueError:
            return str(absolute_path)
