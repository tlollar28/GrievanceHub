"""Focused tests for W5 source lifecycle recovery.

Covers models, Alembic revision structure, SourceManager manifest fields,
SourceSyncService SUPERVISOR_MANUAL + pending reset, and SourceProcessingService
success/failure lifecycle. No live OpenAI calls.
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine, inspect as sa_inspect
from sqlalchemy.orm import sessionmaker

from app.database.models import SourceChunk, SourceDocument
from app.services import source_manager
from app.services.knowledge_base_service import KnowledgeBaseService
from app.services.source_processing_service import SourceProcessingService, split_text
from app.services.source_sync_service import SourceSyncService


# ---------------------------------------------------------------------------
# A. Models + migration structure
# ---------------------------------------------------------------------------


def test_source_document_has_w5_processing_fields():
    columns = {c.key: c for c in sa_inspect(SourceDocument).mapper.column_attrs}
    for name in (
        "version",
        "document_metadata",
        "processing_strategy",
        "processing_status",
        "processed_sha256",
        "processed_at",
        "processing_error",
    ):
        assert name in columns, f"missing SourceDocument.{name}"

    status_col = SourceDocument.__table__.c.processing_status
    assert status_col.nullable is False
    assert status_col.default.arg == "pending"
    assert any(
        idx.name and "processing_status" in idx.name
        for idx in SourceDocument.__table__.indexes
    ) or status_col.index is True


def test_source_chunk_has_chunk_metadata_field():
    columns = {c.key for c in sa_inspect(SourceChunk).mapper.column_attrs}
    assert "chunk_metadata" in columns
    assert SourceChunk.__table__.c.chunk_metadata.nullable is True


def test_alembic_head_is_source_processing_metadata_revision():
    config = Config("alembic.ini")
    script = ScriptDirectory.from_config(config)
    heads = list(script.get_heads())
    assert heads == ["h9c0d1e2f3a4"]

    rev = script.get_revision("h9c0d1e2f3a4")
    assert rev.down_revision == "g8b9c0d1e2f3"

    migration_path = Path(
        "alembic/versions/h9c0d1e2f3a4_add_source_processing_metadata.py"
    )
    assert migration_path.exists()
    assert migration_path.stat().st_size > 0
    text = migration_path.read_text(encoding="utf-8")
    assert "def upgrade()" in text
    assert "def downgrade()" in text
    assert "source_documents" in text
    assert "source_chunks" in text
    assert "processing_status" in text
    assert "chunk_metadata" in text
    assert 'server_default="pending"' in text
    assert "ix_source_documents_processing_status" in text
    # Ensure we did not leave an empty checkpoint-style file.
    assert len(text.strip()) > 100


def test_migration_upgrade_and_downgrade_ops_are_ordered():
    """Static check: downgrade drops index before processing_status column."""
    text = Path(
        "alembic/versions/h9c0d1e2f3a4_add_source_processing_metadata.py"
    ).read_text(encoding="utf-8")
    downgrade_section = text.split("def downgrade()")[1]
    idx_pos = downgrade_section.index("ix_source_documents_processing_status")
    col_pos = downgrade_section.index(
        'drop_column("source_documents", "processing_status")'
    )
    assert idx_pos < col_pos


def test_fresh_migration_chain_enables_pgvector_before_vector_column():
    migration = Path(
        "alembic/versions/2d6d4a6b4613_add_embeddings.py"
    ).read_text(encoding="utf-8")
    extension_pos = migration.index("CREATE EXTENSION IF NOT EXISTS vector")
    vector_column_pos = migration.index("Vector(1536)")
    assert extension_pos < vector_column_pos


# ---------------------------------------------------------------------------
# B. SourceManager
# ---------------------------------------------------------------------------


def test_source_manager_manifest_includes_id_and_optional_version(tmp_path, monkeypatch):
    monkeypatch.setattr(source_manager, "SOURCE_DIR", tmp_path)

    source = {
        "id": "usps_elm_55",
        "name": "USPS ELM 55",
        "source_type": "ELM",
        "official_page": "https://example.com/elm",
        "allowed_file_types": [".pdf"],
        "preferred_keywords": ["elm"],
        "save_folder": "elm",
        "version": "55",
    }
    manifest = {"sources": {}}

    fake_response = SimpleNamespace(
        content=b"%PDF-1.4 fake",
        url="https://example.com/elm55.pdf",
        headers={"content-type": "application/pdf"},
    )

    with (
        patch.object(
            source_manager,
            "discover_links",
            return_value=["https://example.com/elm55.pdf"],
        ),
        patch.object(
            source_manager,
            "choose_best_link",
            return_value="https://example.com/elm55.pdf",
        ),
        patch.object(source_manager, "download_file", return_value=fake_response),
    ):
        source_manager.update_source(source, manifest)

    entry = manifest["sources"]["usps_elm_55"]
    assert entry["id"] == "usps_elm_55"
    assert entry["version"] == "55"
    assert entry["source_type"] == "ELM"
    assert entry["sha256"]
    assert Path(entry["local_path"]).exists()


def test_source_manager_manifest_supports_missing_version(tmp_path, monkeypatch):
    monkeypatch.setattr(source_manager, "SOURCE_DIR", tmp_path)

    source = {
        "id": "npmhu_cim_v6",
        "name": "NPMHU CIM v6",
        "source_type": "CIM",
        "official_page": "https://example.com/cim",
        "allowed_file_types": [".pdf"],
        "preferred_keywords": ["cim"],
        "save_folder": "cim",
    }
    manifest = {"sources": {}}
    fake_response = SimpleNamespace(
        content=b"%PDF-1.4 fake",
        url="https://example.com/cim.pdf",
        headers={"content-type": "application/pdf"},
    )

    with (
        patch.object(
            source_manager,
            "discover_links",
            return_value=["https://example.com/cim.pdf"],
        ),
        patch.object(
            source_manager,
            "choose_best_link",
            return_value="https://example.com/cim.pdf",
        ),
        patch.object(source_manager, "download_file", return_value=fake_response),
    ):
        source_manager.update_source(source, manifest)

    entry = manifest["sources"]["npmhu_cim_v6"]
    assert entry["id"] == "npmhu_cim_v6"
    assert entry["version"] is None


# ---------------------------------------------------------------------------
# C. SourceSyncService
# ---------------------------------------------------------------------------


def test_supervisor_manual_folder_mapping():
    folder = SourceSyncService.get_local_folder_for_source("SUPERVISOR_MANUAL")
    assert folder == Path("uploads/supervisor_manual")
    # Existing sync-only mappings preserved.
    assert SourceSyncService.get_local_folder_for_source("STEP4") == Path(
        "uploads/step4"
    )
    assert SourceSyncService.get_local_folder_for_source("MOU") == Path("uploads/mou")


def test_supervisor_manuals_are_registered_as_distinct_production_sources():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    SourceDocument.__table__.create(engine)
    TestingSession = sessionmaker(bind=engine, autoflush=False, autocommit=False)

    with TestingSession() as db:
        first = KnowledgeBaseService.seed_official_sources(db)
        manuals = (
            db.query(SourceDocument)
            .filter(SourceDocument.source_type == "SUPERVISOR_MANUAL")
            .order_by(SourceDocument.source_id)
            .all()
        )
        second = KnowledgeBaseService.seed_official_sources(db)

        assert len(manuals) == 3
        assert len({source.source_id for source in manuals}) == 3
        assert len({source.local_path for source in manuals}) == 3
        assert all(source.processing_status == "pending" for source in manuals)
        assert all(source.content_type == "application/pdf" for source in manuals)
        assert all(source.version for source in manuals)
        assert all(source.document_metadata["local_filename"] for source in manuals)
        assert all(source.source_id in first["created"] for source in manuals)
        assert all(source.source_id in second["already_existing"] for source in manuals)


def test_local_file_sync_sets_processing_status_pending(tmp_path, monkeypatch):
    pdf = tmp_path / "manual.pdf"
    pdf.write_bytes(b"%PDF-1.4 content")

    source = SimpleNamespace(
        id=7,
        name="Supervisor Manual",
        source_type="SUPERVISOR_MANUAL",
        download_url=None,
        local_path=None,
        sha256=None,
        processing_status="completed",
    )

    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = source

    monkeypatch.setattr(
        SourceSyncService,
        "get_local_folder_for_source",
        staticmethod(lambda _t: tmp_path),
    )
    monkeypatch.setattr(
        SourceSyncService,
        "SOURCE_DIR",
        tmp_path / "data_sources",
        raising=False,
    )
    # Patch module-level SOURCE_DIR used inside sync_source
    monkeypatch.setattr(
        "app.services.source_sync_service.SOURCE_DIR",
        tmp_path / "data_sources",
    )

    result = SourceSyncService.sync_source(db, 7)

    assert result["message"] == "Using existing local PDF."
    assert source.processing_status == "pending"
    assert source.local_path == str(pdf)
    assert source.sha256
    db.commit.assert_called()
    db.refresh.assert_called_with(source)


def test_unchanged_local_file_sync_preserves_completed_status(tmp_path, monkeypatch):
    pdf = tmp_path / "manual.pdf"
    pdf.write_bytes(b"%PDF-1.4 unchanged")
    file_hash = SourceSyncService.calculate_sha256(pdf)

    source = SimpleNamespace(
        id=7,
        name="Supervisor Manual",
        source_type="SUPERVISOR_MANUAL",
        download_url=None,
        local_path=str(pdf),
        sha256=file_hash,
        processing_status="completed",
    )
    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = source

    monkeypatch.setattr(
        SourceSyncService,
        "get_local_folder_for_source",
        staticmethod(lambda _t: tmp_path),
    )
    monkeypatch.setattr(
        "app.services.source_sync_service.SOURCE_DIR",
        tmp_path / "data_sources",
    )

    result = SourceSyncService.sync_source(db, 7)

    assert result["message"] == "Using existing local PDF."
    assert source.processing_status == "completed"
    assert source.local_path == str(pdf)
    assert source.sha256 == file_hash


def test_multi_pdf_sync_resolves_each_supervisor_manual_by_filename(
    tmp_path,
    monkeypatch,
):
    pdfs = {
        "manual-a.pdf": b"%PDF manual A",
        "manual-b.pdf": b"%PDF manual B",
        "manual-c.pdf": b"%PDF manual C",
    }
    for filename, content in pdfs.items():
        (tmp_path / filename).write_bytes(content)

    monkeypatch.setattr(
        SourceSyncService,
        "get_local_folder_for_source",
        staticmethod(lambda _t: tmp_path),
    )
    monkeypatch.setattr(
        "app.services.source_sync_service.SOURCE_DIR",
        tmp_path / "data_sources",
    )

    observed_hashes = set()
    for index, filename in enumerate(pdfs, start=1):
        source = SimpleNamespace(
            id=index,
            name=filename,
            source_type="SUPERVISOR_MANUAL",
            download_url=None,
            local_path=f"uploads/supervisor_manual/{filename}",
            sha256=None,
            processing_status="completed",
            document_metadata={"local_filename": filename},
        )
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = source

        result = SourceSyncService.sync_source(db, index)

        assert result["message"] == "Using existing local PDF."
        assert Path(source.local_path).name == filename
        assert source.processing_status == "pending"
        observed_hashes.add(source.sha256)

    assert len(observed_hashes) == 3


def test_multi_pdf_sync_rejects_ambiguous_source(tmp_path, monkeypatch):
    (tmp_path / "manual-a.pdf").write_bytes(b"%PDF manual A")
    (tmp_path / "manual-b.pdf").write_bytes(b"%PDF manual B")
    source = SimpleNamespace(
        id=9,
        name="Ambiguous Manual",
        source_type="SUPERVISOR_MANUAL",
        download_url=None,
        local_path=None,
        sha256=None,
        processing_status="completed",
        document_metadata=None,
    )
    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = source
    monkeypatch.setattr(
        SourceSyncService,
        "get_local_folder_for_source",
        staticmethod(lambda _t: tmp_path),
    )
    monkeypatch.setattr(
        "app.services.source_sync_service.SOURCE_DIR",
        tmp_path / "data_sources",
    )

    result = SourceSyncService.sync_source(db, 9)

    assert "Multiple local PDFs found" in result["error"]
    assert result["available_files"] == ["manual-a.pdf", "manual-b.pdf"]
    assert source.processing_status == "completed"
    db.commit.assert_not_called()


def test_download_sync_sets_processing_status_pending(tmp_path, monkeypatch):
    download_dir = tmp_path / "data_sources"
    download_dir.mkdir()
    monkeypatch.setattr(
        "app.services.source_sync_service.SOURCE_DIR",
        download_dir,
    )

    source = SimpleNamespace(
        id=8,
        name="ELM",
        source_type="ELM",
        download_url="https://example.com/elm.pdf",
        local_path=None,
        sha256=None,
        processing_status="completed",
    )
    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = source

    # No local folder PDFs — force download path.
    empty_folder = tmp_path / "empty_elm"
    empty_folder.mkdir()
    monkeypatch.setattr(
        SourceSyncService,
        "get_local_folder_for_source",
        staticmethod(lambda _t: empty_folder),
    )

    def fake_urlretrieve(url, path):
        Path(path).write_bytes(b"%PDF-1.4 downloaded")

    with patch(
        "app.services.source_sync_service.urlretrieve",
        side_effect=fake_urlretrieve,
    ):
        result = SourceSyncService.sync_source(db, 8)

    assert "synced successfully" in result["message"].lower()
    assert source.processing_status == "pending"
    assert source.sha256
    assert Path(source.local_path).exists()
    db.commit.assert_called()


# ---------------------------------------------------------------------------
# D–E. SourceProcessingService
# ---------------------------------------------------------------------------


class _FakePage:
    def __init__(self, text: str):
        self._text = text

    def extract_text(self):
        return self._text


class _FakeReader:
    def __init__(self, pages):
        self.pages = pages


def _build_source(tmp_path, **overrides):
    pdf = tmp_path / "doc.pdf"
    pdf.write_bytes(b"%PDF-1.4")
    base = dict(
        id=42,
        source_type="CONTRACT",
        local_path=str(pdf),
        sha256="abc123sha",
        processing_status="pending",
        processing_error="stale",
        processed_at=None,
        processed_sha256=None,
        processing_strategy=None,
    )
    base.update(overrides)
    return SimpleNamespace(**base)


def test_process_source_success_lifecycle(tmp_path):
    source = _build_source(tmp_path)
    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = source

    fake_embedding = [0.1] * 8
    fake_client = MagicMock()
    fake_client.embeddings.create.return_value = SimpleNamespace(
        data=[SimpleNamespace(embedding=fake_embedding)]
    )

    added_chunks = []

    def capture_add(obj):
        added_chunks.append(obj)

    db.add.side_effect = capture_add

    with (
        patch(
            "app.services.source_processing_service.PdfReader",
            return_value=_FakeReader(
                [_FakePage("First paragraph.\n\nSecond paragraph.")]
            ),
        ),
        patch(
            "app.services.source_processing_service.OpenAI",
            return_value=fake_client,
        ),
    ):
        result = SourceProcessingService.process_source(db, 42)

    assert result["message"] == "Source processed successfully."
    assert result["chunks_created"] == 2
    assert source.processing_status == "completed"
    assert source.processed_at is not None
    assert source.processed_sha256 == "abc123sha"
    assert source.processing_strategy == "generic_pdf_v1"
    assert source.processing_error is None
    assert added_chunks
    for chunk in added_chunks:
        assert chunk.chunk_metadata["chunking_strategy"] == "generic_pdf_v1"
        assert chunk.chunk_metadata["source_type"] == "CONTRACT"
        assert "page" in chunk.chunk_metadata
        assert chunk.embedding == fake_embedding
    # prior chunks deleted, then final success commit
    assert db.query.return_value.filter.return_value.delete.called
    assert db.commit.call_count >= 2


def test_process_source_failure_rolls_back_and_marks_failed(tmp_path):
    source = _build_source(tmp_path)
    reloaded = _build_source(tmp_path, processing_status="processing", processing_error=None)

    db = MagicMock()
    # First lookup (pre-process), then post-rollback re-query.
    db.query.return_value.filter.return_value.first.side_effect = [
        source,
        reloaded,
    ]

    with patch(
        "app.services.source_processing_service.PdfReader",
        side_effect=RuntimeError("pdf exploded"),
    ):
        result = SourceProcessingService.process_source(db, 42)

    assert result["error"] == "pdf exploded"
    assert result["type"] == "RuntimeError"
    db.rollback.assert_called()
    assert reloaded.processing_status == "failed"
    assert reloaded.processing_error == "pdf exploded"
    # Failure state committed after rollback.
    assert db.commit.call_count >= 2


def test_process_source_partial_replacement_uses_real_transaction_rollback(tmp_path):
    """A later embedding failure restores old chunks and removes staged replacements."""
    engine = create_engine("sqlite+pysqlite:///:memory:")
    SourceDocument.__table__.create(engine)
    SourceChunk.__table__.create(engine)
    TestingSession = sessionmaker(bind=engine, autoflush=False, autocommit=False)

    pdf = tmp_path / "transaction.pdf"
    pdf.write_bytes(b"%PDF-1.4")

    with TestingSession() as db:
        source = SourceDocument(
            source_id="rollback-probe",
            name="Rollback Probe",
            source_type="CONTRACT",
            local_path=str(pdf),
            sha256="rollback-sha",
            processing_status="completed",
        )
        db.add(source)
        db.flush()
        db.add(
            SourceChunk(
                source_document_id=source.id,
                chunk_index=0,
                page_number=9,
                text="original chunk",
                chunk_metadata={"original": True},
            )
        )
        db.commit()
        source_id = source.id

        first_embedding = SimpleNamespace(
            data=[SimpleNamespace(embedding=[0.1] * 1536)]
        )
        fake_client = MagicMock()
        fake_client.embeddings.create.side_effect = [
            first_embedding,
            RuntimeError("second embedding failed"),
        ]

        with (
            patch(
                "app.services.source_processing_service.PdfReader",
                return_value=_FakeReader(
                    [_FakePage("First replacement.\n\nSecond replacement.")]
                ),
            ),
            patch(
                "app.services.source_processing_service.OpenAI",
                return_value=fake_client,
            ),
        ):
            result = SourceProcessingService.process_source(db, source_id)

        assert result == {
            "error": "second embedding failed",
            "type": "RuntimeError",
        }
        db.expire_all()

        persisted_source = db.get(SourceDocument, source_id)
        persisted_chunks = (
            db.query(SourceChunk)
            .filter(SourceChunk.source_document_id == source_id)
            .all()
        )

        assert persisted_source.processing_status == "failed"
        assert persisted_source.processing_error == "second embedding failed"
        assert len(persisted_chunks) == 1
        assert persisted_chunks[0].text == "original chunk"
        assert persisted_chunks[0].page_number == 9
        assert persisted_chunks[0].chunk_metadata == {"original": True}


def test_split_text_preserves_pipeline_helper():
    parts = split_text("a" * 50, max_chars=20)
    assert all(len(p) <= 20 for p in parts)
    assert "".join(parts).replace(" ", "")  # non-empty content preserved
