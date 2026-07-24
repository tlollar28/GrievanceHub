"""Phase W3 Case Asset foundation tests.

Covers schema/categories, path safety helpers, service behavior with mocks,
API route wiring, and optional PostgreSQL persistence when available.
"""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.exc import ProgrammingError

from app.config import CASE_ASSET_DIR, CASE_ASSET_MAX_UPLOAD_BYTES
from app.database.models import (
    CaseAsset,
    CaseDomainEvent,
    CaseMemoryRecord,
    CaseTimelineEventRecord,
    GrievanceCase,
)
from app.database.session import SessionLocal
from app.main import app
from app.schemas.case_asset_schema import (
    EXECUTABLE_ASSET_CATEGORIES,
    PLACEHOLDER_ASSET_CATEGORIES,
    CaseAssetMetadata,
)
from app.services.case_asset_service import (
    CaseAssetCategoryNotExecutableError,
    CaseAssetNotFoundError,
    CaseAssetService,
    CaseAssetValidationError,
)
from app.services.case_service import CaseService

SYNTHETIC_CASE_UUID = "00000000-0000-4000-8000-000000000501"
SYNTHETIC_ASSET_UUID = "00000000-0000-4000-8000-000000000502"


# ---------------------------------------------------------------------------
# Schema / contract
# ---------------------------------------------------------------------------


def test_asset_categories_cover_long_term_types():
    assert "uploaded_document" in EXECUTABLE_ASSET_CATEGORIES
    assert PLACEHOLDER_ASSET_CATEGORIES == {
        "generated_report",
        "generated_grievance",
        "future_export",
        "future_attachment",
    }
    infos = CaseAssetService.list_category_info()
    assert len(infos) == 5
    assert sum(1 for info in infos if info.executable_in_w3) == 1


def test_case_asset_metadata_model_accepts_core_fields():
    meta = CaseAssetMetadata(
        asset_uuid=SYNTHETIC_ASSET_UUID,
        case_uuid=SYNTHETIC_CASE_UUID,
        asset_category="uploaded_document",
        original_filename="approval.pdf",
        stored_filename=f"{SYNTHETIC_ASSET_UUID}_approval.pdf",
        mime_type="application/pdf",
        file_size=12,
        sha256="abc",
        source="api",
    )
    assert meta.version_number == 1
    assert meta.status == "active"


def test_safe_filename_strips_path_traversal():
    assert CaseAssetService._safe_filename("../../etc/passwd") == "passwd"
    assert CaseAssetService._safe_filename("a\\b\\note.pdf") == "note.pdf"
    assert CaseAssetService._safe_filename(None) == "upload.bin"
    assert CaseAssetService._safe_filename("..") == "upload.bin"


# ---------------------------------------------------------------------------
# CaseService context merge
# ---------------------------------------------------------------------------


def test_build_case_context_prefers_first_class_assets():
    asset = SimpleNamespace(
        asset_uuid=SYNTHETIC_ASSET_UUID,
        case_uuid=SYNTHETIC_CASE_UUID,
        asset_category="uploaded_document",
        original_filename="approval.pdf",
        stored_filename=f"{SYNTHETIC_ASSET_UUID}_approval.pdf",
        stored_path=f"data/case_assets/{SYNTHETIC_CASE_UUID}/x.pdf",
        mime_type="application/pdf",
        file_size=10,
        sha256="deadbeef",
        uploaded_by="Steward",
        source="api",
        version_number=1,
        parent_asset_uuid=None,
        report_version_id=None,
        report_version_number=None,
        draft_record_uuid=None,
        status="active",
        asset_metadata=None,
        created_at=datetime(2026, 7, 10, tzinfo=timezone.utc),
        updated_at=datetime(2026, 7, 10, tzinfo=timezone.utc),
    )
    case = SimpleNamespace(
        case_uuid=SYNTHETIC_CASE_UUID,
        title="Leave",
        user_name="Steward",
        local_number="300",
        initial_question="Question?",
        known_facts={},
        status="open",
        messages=[
            SimpleNamespace(
                role="user",
                content="See attachment",
                message_metadata={
                    "uploaded_files": [
                        {"file_id": SYNTHETIC_ASSET_UUID, "ref": SYNTHETIC_ASSET_UUID}
                    ]
                },
                created_at=datetime(2026, 7, 10, tzinfo=timezone.utc),
            )
        ],
        assets=[asset],
    )
    ctx = CaseService.build_case_context(case)
    assert len(ctx["uploaded_files"]) == 1
    assert ctx["uploaded_files"][0]["asset_uuid"] == SYNTHETIC_ASSET_UUID
    assert ctx["uploaded_files"][0]["filename"] == "approval.pdf"
    assert len(ctx["case_assets"]) == 1


def test_serialize_case_assets_skips_non_active():
    case = SimpleNamespace(
        assets=[
            SimpleNamespace(
                asset_uuid="a1",
                case_uuid=SYNTHETIC_CASE_UUID,
                asset_category="uploaded_document",
                original_filename="a.pdf",
                stored_filename="a.pdf",
                stored_path="data/case_assets/a.pdf",
                mime_type="application/pdf",
                file_size=1,
                sha256=None,
                uploaded_by=None,
                source="api",
                version_number=1,
                parent_asset_uuid=None,
                report_version_id=None,
                report_version_number=None,
                draft_record_uuid=None,
                status="archived",
                asset_metadata=None,
                created_at=None,
                updated_at=None,
            )
        ]
    )
    assert CaseService.serialize_case_assets(case) == []


# ---------------------------------------------------------------------------
# Service unit tests (mocked DB)
# ---------------------------------------------------------------------------


def test_create_asset_rejects_placeholder_categories():
    service = CaseAssetService(MagicMock())
    with pytest.raises(CaseAssetCategoryNotExecutableError):
        service.create_asset(
            SYNTHETIC_CASE_UUID,
            category="generated_report",
            filename="report.pdf",
            content=b"%PDF",
        )


def test_upload_document_persists_metadata_and_bytes(tmp_path, monkeypatch):
    monkeypatch.setattr("app.services.case_asset_service.CASE_ASSET_DIR", tmp_path)
    db = MagicMock()
    case = SimpleNamespace(
        id=7,
        case_uuid=SYNTHETIC_CASE_UUID,
        user_name="Steward A",
        updated_at=None,
    )
    db.query.return_value.filter.return_value.first.return_value = case

    stored_rows: list[CaseAsset] = []

    def _add(row):
        stored_rows.append(row)

    db.add.side_effect = _add

    service = CaseAssetService(db)
    content = b"synthetic evidence bytes"
    result = service.upload_document(
        SYNTHETIC_CASE_UUID,
        filename="approval letter.pdf",
        content=content,
        mime_type="application/pdf",
        source="manual_ui",
    )

    assert result.asset.asset_category == "uploaded_document"
    assert result.asset.original_filename == "approval letter.pdf"
    assert result.asset.file_size == len(content)
    assert result.asset.sha256 == hashlib.sha256(content).hexdigest()
    assert result.asset.uploaded_by == "Steward A"
    asset_rows = [row for row in stored_rows if isinstance(row, CaseAsset)]
    assert len(asset_rows) == 1
    # Steward Official Case Record also records Evidence uploaded.
    assert any(
        getattr(row, "event_type", None) == "files_uploaded" for row in stored_rows
    )
    written = tmp_path / SYNTHETIC_CASE_UUID / asset_rows[0].stored_filename
    assert written.read_bytes() == content
    db.commit.assert_called_once()


def test_upload_rejects_oversized_file(monkeypatch):
    monkeypatch.setattr(
        "app.services.case_asset_service.CASE_ASSET_MAX_UPLOAD_BYTES", 8
    )
    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = SimpleNamespace(
        id=1, case_uuid=SYNTHETIC_CASE_UUID, user_name=None, updated_at=None
    )
    service = CaseAssetService(db)
    with pytest.raises(CaseAssetValidationError, match="maximum size"):
        service.upload_document(
            SYNTHETIC_CASE_UUID,
            filename="big.bin",
            content=b"0123456789",
        )


def test_get_asset_raises_when_missing():
    db = MagicMock()
    # First call: case exists; second: asset missing
    case = SimpleNamespace(id=1, case_uuid=SYNTHETIC_CASE_UUID)
    db.query.return_value.filter.return_value.first.side_effect = [case, None]
    service = CaseAssetService(db)
    with pytest.raises(CaseAssetNotFoundError):
        service.get_asset(SYNTHETIC_CASE_UUID, SYNTHETIC_ASSET_UUID)


def test_resolve_upload_refs_mixes_assets_and_legacy():
    db = MagicMock()
    asset_row = SimpleNamespace(
        asset_uuid=SYNTHETIC_ASSET_UUID,
        case_uuid=SYNTHETIC_CASE_UUID,
        asset_category="uploaded_document",
        original_filename="a.pdf",
        stored_filename="a.pdf",
        stored_path="data/case_assets/a.pdf",
        mime_type="application/pdf",
        file_size=3,
        sha256="aa",
        uploaded_by=None,
        source="api",
        version_number=1,
        status="active",
    )
    db.query.return_value.filter.return_value.first.side_effect = [
        asset_row,
        None,
    ]
    service = CaseAssetService(db)
    resolved = service.resolve_upload_refs_for_context(
        SYNTHETIC_CASE_UUID,
        [SYNTHETIC_ASSET_UUID, "legacy-ref-1"],
    )
    assert resolved[0]["asset_uuid"] == SYNTHETIC_ASSET_UUID
    assert resolved[1] == {
        "file_id": "legacy-ref-1",
        "ref": "legacy-ref-1",
        "asset_uuid": None,
    }


# ---------------------------------------------------------------------------
# API route tests
# ---------------------------------------------------------------------------


@pytest.fixture
def client():
    return TestClient(app)


def test_list_assets_route(client):
    expected = {
        "case_uuid": SYNTHETIC_CASE_UUID,
        "count": 1,
        "assets": [
            {
                "asset_uuid": SYNTHETIC_ASSET_UUID,
                "case_uuid": SYNTHETIC_CASE_UUID,
                "asset_category": "uploaded_document",
                "original_filename": "a.pdf",
                "status": "active",
                "version_number": 1,
                "source": "api",
            }
        ],
    }
    with patch.object(
        CaseAssetService,
        "list_assets",
        return_value=SimpleNamespace(model_dump=lambda mode="json": expected),
    ):
        response = client.get(f"/cases/{SYNTHETIC_CASE_UUID}/assets")
    assert response.status_code == 200
    assert response.json()["count"] == 1


def test_upload_asset_route(client):
    expected = {
        "case_uuid": SYNTHETIC_CASE_UUID,
        "asset": {
            "asset_uuid": SYNTHETIC_ASSET_UUID,
            "case_uuid": SYNTHETIC_CASE_UUID,
            "asset_category": "uploaded_document",
            "original_filename": "note.txt",
            "status": "active",
            "version_number": 1,
            "source": "api",
        },
        "message": "Case asset uploaded successfully.",
    }
    with patch.object(
        CaseAssetService,
        "create_asset",
        return_value=SimpleNamespace(model_dump=lambda mode="json": expected),
    ) as mock_create:
        response = client.post(
            f"/cases/{SYNTHETIC_CASE_UUID}/assets",
            files={"file": ("note.txt", b"hello", "text/plain")},
            data={"category": "uploaded_document", "source": "manual_ui"},
        )
    assert response.status_code == 200
    assert response.json()["asset"]["asset_uuid"] == SYNTHETIC_ASSET_UUID
    mock_create.assert_called_once()


def test_upload_asset_route_rejects_placeholder_category(client):
    with patch.object(
        CaseAssetService,
        "create_asset",
        side_effect=CaseAssetCategoryNotExecutableError("generated_grievance"),
    ):
        response = client.post(
            f"/cases/{SYNTHETIC_CASE_UUID}/assets",
            files={"file": ("g.pdf", b"%PDF", "application/pdf")},
            data={"category": "generated_grievance"},
        )
    assert response.status_code == 400
    assert "placeholder" in response.json()["detail"].lower()


def test_get_asset_route_404(client):
    with patch.object(
        CaseAssetService,
        "get_asset",
        side_effect=CaseAssetNotFoundError(SYNTHETIC_ASSET_UUID),
    ):
        response = client.get(
            f"/cases/{SYNTHETIC_CASE_UUID}/assets/{SYNTHETIC_ASSET_UUID}"
        )
    assert response.status_code == 404


def test_workspace_includes_assets_key(client):
    workspace = {
        "case_uuid": SYNTHETIC_CASE_UUID,
        "title": "Leave",
        "assets": [{"asset_uuid": SYNTHETIC_ASSET_UUID}],
        "uploaded_assets": [{"asset_uuid": SYNTHETIC_ASSET_UUID}],
    }
    with patch.object(CaseService, "get_case_workspace", return_value=workspace):
        response = client.get(f"/cases/{SYNTHETIC_CASE_UUID}/workspace")
    assert response.status_code == 200
    body = response.json()
    assert "assets" in body
    assert body["uploaded_assets"][0]["asset_uuid"] == SYNTHETIC_ASSET_UUID


# ---------------------------------------------------------------------------
# Optional DB persistence
# ---------------------------------------------------------------------------


def _db_available() -> bool:
    try:
        from sqlalchemy import create_engine
        from app.config import DATABASE_URL

        engine = create_engine(
            DATABASE_URL,
            pool_pre_ping=True,
            connect_args={"connect_timeout": 2},
        )
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        engine.dispose()
        return True
    except Exception:
        return False


def _case_assets_migrated(session) -> bool:
    try:
        session.query(CaseAsset.id).limit(1).all()
        return True
    except ProgrammingError:
        session.rollback()
        return False


@pytest.fixture
def postgres_session():
    if not _db_available():
        pytest.skip("PostgreSQL database not available for persistence tests")
    session = SessionLocal()
    if not _case_assets_migrated(session):
        session.close()
        pytest.skip("Phase W3 migration not applied (run alembic upgrade head)")
    try:
        yield session
    finally:
        session.close()


def test_upload_document_roundtrip_postgres(tmp_path, monkeypatch, postgres_session):
    monkeypatch.setattr("app.services.case_asset_service.CASE_ASSET_DIR", tmp_path)
    session = postgres_session

    case_uuid = str(uuid4())
    case = GrievanceCase(
        case_uuid=case_uuid,
        title="Synthetic asset case",
        initial_question="Synthetic question for asset foundation.",
        known_facts={"synthetic": True},
        status="open",
        user_name="Synthetic Steward",
    )
    session.add(case)
    session.commit()
    session.refresh(case)

    service = CaseAssetService(session)
    content = b"postgres roundtrip evidence"
    uploaded = service.upload_document(
        case_uuid,
        filename="evidence.txt",
        content=content,
        mime_type="text/plain",
        source="api",
    )
    listed = service.list_assets(case_uuid)
    meta = service.get_asset(case_uuid, uploaded.asset.asset_uuid)

    assert listed.count == 1
    assert meta.sha256 == hashlib.sha256(content).hexdigest()
    assert meta.original_filename == "evidence.txt"
    stored = Path(tmp_path) / case_uuid / meta.stored_filename
    assert stored.read_bytes() == content

    session.query(CaseTimelineEventRecord).filter(
        CaseTimelineEventRecord.case_uuid == case_uuid
    ).delete(synchronize_session=False)
    session.query(CaseDomainEvent).filter(
        CaseDomainEvent.case_uuid == case_uuid
    ).delete(synchronize_session=False)
    session.query(CaseMemoryRecord).filter(
        CaseMemoryRecord.case_uuid == case_uuid
    ).delete(synchronize_session=False)
    session.query(CaseAsset).filter(CaseAsset.case_uuid == case_uuid).delete(
        synchronize_session=False
    )
    session.query(GrievanceCase).filter(GrievanceCase.case_uuid == case_uuid).delete()
    session.commit()


def test_max_upload_constant_is_positive():
    assert CASE_ASSET_MAX_UPLOAD_BYTES >= 1_000_000
    assert CASE_ASSET_DIR.name == "case_assets"
