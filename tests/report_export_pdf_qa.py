"""PDF-level visual QA helpers for Phase 3 export tests."""

from __future__ import annotations

import re
from io import BytesIO

from pypdf import PdfReader

_DISCLAIMER_MARKERS = (
    "research draft",
    "not legal advice",
    "steward review",
    "grievancehub analysis report",
    "page ",
)


def extract_pdf_pages(pdf_bytes: bytes) -> list[str]:
    reader = PdfReader(BytesIO(pdf_bytes))
    return [(page.extract_text() or "") for page in reader.pages]


def _substantive_chars(page_text: str) -> int:
    cleaned = page_text.lower()
    for marker in _DISCLAIMER_MARKERS:
        cleaned = cleaned.replace(marker, " ")
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return len(cleaned)


def is_disclaimer_only_page(page_text: str) -> bool:
    text = page_text.strip()
    if not text:
        return True
    substantive = _substantive_chars(text)
    lowered = text.lower()
    has_disclaimer = "research draft" in lowered or "not legal advice" in lowered
    has_section_content = any(
        marker in lowered
        for marker in (
            "citation validation",
            "source references",
            "limitations and missing sources",
            "detailed analysis",
            "recommended remedy",
            "your question",
        )
    )
    return has_disclaimer and not has_section_content and substantive < 120


def assert_pdf_has_no_disclaimer_only_final_page(pdf_bytes: bytes) -> None:
    pages = extract_pdf_pages(pdf_bytes)
    assert pages, "PDF must contain at least one page"
    last_page = pages[-1]
    assert "research draft" in last_page.lower() or "not legal advice" in last_page.lower()
    assert not is_disclaimer_only_page(last_page), (
        "Final PDF page must not contain only the research-draft disclaimer"
    )
