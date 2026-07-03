"""Sanitized export filenames without PII."""

from __future__ import annotations

import re


def build_export_filename(case_uuid: str, version_number: int, extension: str) -> str:
    """Build a safe attachment filename using opaque case UUID prefix only."""
    uuid_prefix = re.sub(r"[^a-fA-F0-9-]", "", case_uuid)[:8].lower()
    ext = extension.lstrip(".").lower()
    if ext not in {"html", "pdf"}:
        raise ValueError("Unsupported export extension")
    return f"grievancehub-report-{uuid_prefix}-v{version_number}.{ext}"
