"""In-memory PDF generation with deny-by-default resource loading."""

from __future__ import annotations

from pathlib import Path
from urllib.parse import urlparse

from weasyprint import HTML

from app.config import PROJECT_ROOT, REPORT_STATIC_DIR


class ForbiddenResourceError(Exception):
    """A disallowed external or user-controlled resource was requested."""


class PdfGenerationError(Exception):
    """PDF generation failed."""


class ReportPdfGenerator:
    TRUSTED_STATIC_DIR = REPORT_STATIC_DIR.resolve()

    @classmethod
    def _deny_by_default_url_fetcher(cls, url: str, *args, **kwargs):
        parsed = urlparse(url)
        scheme = (parsed.scheme or "").lower()

        if scheme in {"http", "https", "ftp", "data", "javascript"}:
            raise ForbiddenResourceError(f"Forbidden URL scheme: {scheme or 'unknown'}")

        if scheme == "file":
            raw_path = parsed.path
            if parsed.netloc:
                raw_path = f"//{parsed.netloc}{parsed.path}"
            candidate = Path(raw_path).resolve()
            try:
                candidate.relative_to(cls.TRUSTED_STATIC_DIR)
            except ValueError as exc:
                raise ForbiddenResourceError("Forbidden local file path") from exc
            with candidate.open("rb") as handle:
                return {"string": handle.read(), "mime_type": None}

        raise ForbiddenResourceError(f"Forbidden URL scheme: {scheme or 'unknown'}")

    @classmethod
    def html_to_pdf_bytes(cls, html: str) -> bytes:
        try:
            pdf_bytes = HTML(
                string=html,
                base_url=str(PROJECT_ROOT),
                url_fetcher=cls._deny_by_default_url_fetcher,
            ).write_pdf()
        except ForbiddenResourceError:
            raise
        except Exception as exc:
            raise PdfGenerationError(str(exc)) from exc

        if not pdf_bytes or not pdf_bytes.startswith(b"%PDF"):
            raise PdfGenerationError("Generated output is not a valid PDF")

        return pdf_bytes
