"""W6 remediation D: streamed and bounded case-asset uploads.

Covers the ``_read_upload_within_limit`` chunked-reading helper in
``app/api/routes/cases.py`` (Content-Length pre-check, authoritative streamed
counter, early stop, read-failure propagation) and the storage-cleanup
behavior in ``CaseAssetService._store_uploaded_file`` (no orphaned file after
a write/hash/database failure). Existing behavior — empty-file rejection,
category validation, case scoping, SHA-256, timeline/Case Memory side
effects, and the API response contract — is exercised elsewhere in
``test_case_asset_foundation.py`` and is not duplicated here except where a
regression specifically threatens it.
"""

from __future__ import annotations

import asyncio
import hashlib
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.api.routes.cases import _read_upload_within_limit
from app.main import app
from app.services.case_asset_service import CaseAssetService, CaseAssetValidationError

SYNTHETIC_CASE_UUID = "00000000-0000-4000-8000-000000000701"


class _FakeUploadFile:
    """Duck-typed stand-in for FastAPI's ``UploadFile`` exposing only the
    async ``read(size)`` method the streaming helper actually calls."""

    def __init__(self, chunks: list[bytes]) -> None:
        self._chunks = list(chunks)
        self.read_calls: list[int] = []

    async def read(self, size: int) -> bytes:
        self.read_calls.append(size)
        if not self._chunks:
            return b""
        return self._chunks.pop(0)


class _UnreadableUploadFile:
    """Fails the test if ``read`` is ever called — used to prove the
    Content-Length pre-check rejects before attempting any read."""

    async def read(self, size: int) -> bytes:  # pragma: no cover - must not run
        raise AssertionError("read() must not be called after an early rejection")


class _FailingUploadFile:
    """Returns real chunks, then raises on a later read to simulate a
    dropped connection or other I/O failure mid-stream."""

    def __init__(self, chunks: list[bytes], fail_after: int) -> None:
        self._chunks = list(chunks)
        self._fail_after = fail_after
        self.read_calls = 0

    async def read(self, size: int) -> bytes:
        self.read_calls += 1
        if self.read_calls > self._fail_after:
            raise ConnectionError("synthetic client disconnect")
        if not self._chunks:
            return b""
        return self._chunks.pop(0)


def _read(file, max_bytes: int, *, content_length_header, chunk_size=64) -> bytes:
    return asyncio.run(
        _read_upload_within_limit(
            file,
            max_bytes,
            content_length_header=content_length_header,
            chunk_size=chunk_size,
        )
    )


# ---------------------------------------------------------------------------
# _read_upload_within_limit — Content-Length handling
# ---------------------------------------------------------------------------


def test_rejects_immediately_when_content_length_exceeds_limit():
    """A Content-Length that already exceeds the cap allows early rejection
    without ever attempting to read the body."""
    with pytest.raises(CaseAssetValidationError, match="maximum size"):
        _read(_UnreadableUploadFile(), max_bytes=10, content_length_header="1000")


def test_missing_content_length_still_enforces_the_streamed_limit():
    """No Content-Length header at all — the streamed counter alone must
    still reject an oversized body."""
    file = _FakeUploadFile([b"0123456789", b"0123456789"])
    with pytest.raises(CaseAssetValidationError, match="maximum size"):
        _read(file, max_bytes=15, content_length_header=None)


def test_misleading_content_length_does_not_bypass_the_streamed_limit():
    """A Content-Length that under-reports the true size must not let an
    oversized body through — the streamed byte counter is authoritative."""
    file = _FakeUploadFile([b"0123456789", b"0123456789"])
    with pytest.raises(CaseAssetValidationError, match="maximum size"):
        _read(file, max_bytes=15, content_length_header="1")


# ---------------------------------------------------------------------------
# _read_upload_within_limit — streamed counter behavior
# ---------------------------------------------------------------------------


def test_upload_below_limit_is_accepted():
    file = _FakeUploadFile([b"abcde", b"fgh"])
    result = _read(file, max_bytes=10, content_length_header=None)
    assert result == b"abcdefgh"


def test_upload_exactly_at_limit_is_accepted():
    file = _FakeUploadFile([b"0123456789"])  # exactly 10 bytes
    result = _read(file, max_bytes=10, content_length_header=None)
    assert result == b"0123456789"
    assert len(result) == 10


def test_upload_one_byte_over_limit_is_rejected():
    file = _FakeUploadFile([b"0123456789X"])  # 11 bytes
    with pytest.raises(CaseAssetValidationError, match="maximum size"):
        _read(file, max_bytes=10, content_length_header=None)


def test_multiple_chunks_are_reassembled_in_order():
    file = _FakeUploadFile([b"AAAA", b"BBBB", b"CCCC"])
    result = _read(file, max_bytes=100, content_length_header=None, chunk_size=4)
    assert result == b"AAAABBBBCCCC"
    # 3 data chunks plus the terminating empty read.
    assert len(file.read_calls) == 4


def test_reading_stops_immediately_once_limit_is_exceeded():
    """The third chunk must never be requested once the first two already
    exceed the limit — no oversized body is ever fully buffered."""
    file = _FakeUploadFile([b"A" * 10, b"B" * 10, b"C" * 10])
    with pytest.raises(CaseAssetValidationError, match="maximum size"):
        _read(file, max_bytes=15, content_length_header=None)
    assert len(file.read_calls) == 2


def test_empty_upload_returns_empty_bytes_without_error():
    """The helper itself does not reject empty files — that remains the
    service's responsibility (see test_case_asset_foundation.py)."""
    file = _FakeUploadFile([])
    result = _read(file, max_bytes=10, content_length_header=None)
    assert result == b""


def test_read_failure_propagates_without_returning_partial_content():
    file = _FailingUploadFile([b"chunk-one"], fail_after=1)
    with pytest.raises(ConnectionError):
        _read(file, max_bytes=1000, content_length_header=None)


# ---------------------------------------------------------------------------
# Route wiring — oversized rejection touches the service layer not at all
# ---------------------------------------------------------------------------


@pytest.fixture
def client():
    return TestClient(app)


def test_route_rejects_oversized_upload_without_calling_create_asset(client):
    with patch("app.api.routes.cases.CASE_ASSET_MAX_UPLOAD_BYTES", 8):
        with patch.object(CaseAssetService, "create_asset") as mock_create:
            response = client.post(
                f"/cases/{SYNTHETIC_CASE_UUID}/assets",
                files={"file": ("big.bin", b"0123456789", "application/octet-stream")},
                data={"category": "uploaded_document"},
            )
    assert response.status_code == 400
    assert "maximum size" in response.json()["detail"].lower()
    mock_create.assert_not_called()


def test_route_passes_fully_reassembled_bytes_to_the_service(client):
    captured: dict = {}

    def _capture_create_asset(self, case_uuid, **kwargs):
        captured["case_uuid"] = case_uuid
        captured.update(kwargs)
        return SimpleNamespace(
            model_dump=lambda mode="json": {
                "case_uuid": case_uuid,
                "asset": {"asset_uuid": "a1"},
                "message": "Case asset uploaded successfully.",
            }
        )

    with patch("app.api.routes.cases.CASE_ASSET_MAX_UPLOAD_BYTES", 1024):
        with patch.object(CaseAssetService, "create_asset", _capture_create_asset):
            response = client.post(
                f"/cases/{SYNTHETIC_CASE_UUID}/assets",
                files={"file": ("note.txt", b"hello streamed world", "text/plain")},
                data={"category": "uploaded_document", "source": "manual_ui"},
            )
    assert response.status_code == 200
    assert captured["content"] == b"hello streamed world"
    assert captured["case_uuid"] == SYNTHETIC_CASE_UUID


# ---------------------------------------------------------------------------
# CaseAssetService._store_uploaded_file — cleanup after failure
# ---------------------------------------------------------------------------


def _mock_case() -> SimpleNamespace:
    return SimpleNamespace(
        id=1, case_uuid=SYNTHETIC_CASE_UUID, user_name="Steward A", updated_at=None
    )


def test_still_rejects_empty_file_with_no_side_effects():
    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = _mock_case()
    service = CaseAssetService(db)

    with pytest.raises(CaseAssetValidationError, match="empty"):
        service.upload_document(SYNTHETIC_CASE_UUID, filename="empty.txt", content=b"")

    db.add.assert_not_called()
    db.commit.assert_not_called()


def test_cleans_up_stored_file_when_database_commit_fails(tmp_path, monkeypatch):
    monkeypatch.setattr("app.services.case_asset_service.CASE_ASSET_DIR", tmp_path)
    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = _mock_case()
    db.commit.side_effect = RuntimeError("synthetic database outage")
    service = CaseAssetService(db)

    with pytest.raises(RuntimeError, match="synthetic database outage"):
        service.upload_document(
            SYNTHETIC_CASE_UUID, filename="orphan.txt", content=b"synthetic bytes"
        )

    db.rollback.assert_called_once()
    case_dir = tmp_path / SYNTHETIC_CASE_UUID
    remaining = list(case_dir.iterdir()) if case_dir.exists() else []
    assert remaining == [], f"expected no orphaned files, found {remaining}"


def test_cleans_up_and_raises_when_disk_write_fails(tmp_path, monkeypatch):
    monkeypatch.setattr("app.services.case_asset_service.CASE_ASSET_DIR", tmp_path)
    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = _mock_case()

    def _raise_write(self: Path, data: bytes) -> None:
        raise OSError("synthetic disk write failure")

    monkeypatch.setattr(Path, "write_bytes", _raise_write)
    service = CaseAssetService(db)

    with pytest.raises(OSError, match="synthetic disk write failure"):
        service.upload_document(
            SYNTHETIC_CASE_UUID, filename="never-written.txt", content=b"synthetic bytes"
        )

    db.add.assert_not_called()
    db.commit.assert_not_called()
    db.rollback.assert_called_once()


def test_successful_upload_is_unaffected_by_cleanup_wrapper(tmp_path, monkeypatch):
    """Guards against a regression where the try/except added for cleanup
    accidentally changes the happy-path result, hashing, or commit."""
    monkeypatch.setattr("app.services.case_asset_service.CASE_ASSET_DIR", tmp_path)
    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = _mock_case()
    service = CaseAssetService(db)
    content = b"synthetic evidence for cleanup-wrapper regression check"

    result = service.upload_document(
        SYNTHETIC_CASE_UUID, filename="ok.txt", content=content, source="manual_ui"
    )

    assert result.asset.sha256 == hashlib.sha256(content).hexdigest()
    assert result.asset.file_size == len(content)
    db.commit.assert_called_once()
    db.rollback.assert_not_called()
    stored = tmp_path / SYNTHETIC_CASE_UUID / result.asset.stored_filename
    assert stored.read_bytes() == content
