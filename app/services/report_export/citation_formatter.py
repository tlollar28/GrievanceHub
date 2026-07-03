"""Steward-facing citation formatting for HTML/PDF export."""

from __future__ import annotations

import re
from typing import Any

_PLACEHOLDER_VALUES = frozenset({"", "n/a", "na", "unknown", "none", "null"})

_DOCUMENT_TYPE_LABELS = {
    "CONTRACT": "National Agreement",
    "CIM": "CIM",
    "ELM": "ELM",
    "LMOU": "LMOU",
}


def _clean(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text or text.lower() in _PLACEHOLDER_VALUES:
        return None
    return text


def normalize_quote(text: str | None) -> str:
    if not text:
        return ""
    collapsed = re.sub(r"\s+", " ", str(text).strip())
    return collapsed.lower()


def format_document_title(document_name: str | None, document_type: str | None = None) -> str | None:
    name = _clean(document_name)
    doc_type = _clean(document_type)
    if not name:
        return _DOCUMENT_TYPE_LABELS.get(doc_type or "", doc_type)

    upper_name = name.upper()
    if doc_type:
        type_upper = doc_type.upper()
        redundant_suffixes = (
            f" ({type_upper})",
            f" ({doc_type})",
            f" — {type_upper}",
            f" - {type_upper}",
        )
        for suffix in redundant_suffixes:
            if name.endswith(suffix):
                name = name[: -len(suffix)].strip()
                break

        if type_upper == "CIM" and "CIM" in upper_name:
            return name
        if type_upper == "CONTRACT" and ("NATIONAL AGREEMENT" in upper_name or "NPMHU" in upper_name):
            return name
        if type_upper == "ELM" and upper_name.startswith("ELM"):
            return name

    return name


def _format_article_section(article_or_section: str | None) -> str | None:
    from app.services.report_export.text_formatter import normalize_article_section_label

    return normalize_article_section_label(article_or_section)


def parse_page_number(value: Any) -> int | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text or text.lower() in _PLACEHOLDER_VALUES:
        return None
    try:
        return int(float(text))
    except ValueError:
        return None


def collect_page_numbers(*values: Any) -> list[int]:
    pages: list[int] = []
    seen: set[int] = set()
    for value in values:
        if isinstance(value, (list, tuple, set)):
            for item in value:
                parsed = parse_page_number(item)
                if parsed is not None and parsed not in seen:
                    seen.add(parsed)
                    pages.append(parsed)
            continue
        parsed = parse_page_number(value)
        if parsed is not None and parsed not in seen:
            seen.add(parsed)
            pages.append(parsed)
    pages.sort()
    return pages


def format_page_reference(pages: list[int]) -> str | None:
    if not pages:
        return None
    if len(pages) == 1:
        return f"p. {pages[0]}"
    if all(pages[index] + 1 == pages[index + 1] for index in range(len(pages) - 1)):
        return f"pp. {pages[0]}\u2013{pages[-1]}"
    return "pp. " + ", ".join(str(page) for page in pages)


def normalize_citation_pages(citation: dict[str, Any] | None) -> dict[str, Any]:
    normalized = dict(citation or {})
    pages = collect_page_numbers(normalized.get("pages"), normalized.get("page"))
    if pages:
        normalized["pages"] = pages
        normalized["page"] = pages[0]
    return normalized


def format_steward_citation(
    citation: dict[str, Any] | None,
    *,
    article_or_section: str | None = None,
) -> str:
    """Format a public citation line without internal retrieval metadata."""
    citation = normalize_citation_pages(citation)
    article = _format_article_section(article_or_section or citation.get("article_or_section"))
    document = format_document_title(
        citation.get("document_name"),
        citation.get("document_type"),
    )
    page_text = format_page_reference(collect_page_numbers(citation.get("pages"), citation.get("page")))

    segments: list[str] = []
    if document and article:
        segments.append(f"{document} — {article}")
    elif document:
        segments.append(document)
    elif article:
        segments.append(article)

    if page_text:
        segments.append(page_text)

    return " — ".join(segments)


def format_source_reference_summary(distinct_authority_count: int, passage_count: int) -> str:
    authority_label = "distinct authority" if distinct_authority_count == 1 else "distinct authorities"
    passage_label = "retrieved passage" if passage_count == 1 else "retrieved passages"
    return f"{distinct_authority_count} {authority_label}, {passage_count} {passage_label}"


def format_role_label(role: str | None, role_title: str | None = None) -> str:
    mapping = {
        "union_supporting": "Union-Supporting Authority",
        "procedural_requirement": "Procedural Requirement",
        "information_right": "Information Rights",
        "timeline_requirement": "Timeline Requirement",
        "remedy_support": "Remedy Authority",
        "management_limiting": "Management-Limiting Authority",
        "background_only": "Background Authority",
    }
    if role_title and _clean(role_title):
        return role_title
    return mapping.get((role or "").strip(), "Governing Authority")


def authority_identity_key(item: dict[str, Any]) -> tuple[str, ...]:
    citation = item.get("citation") or {}
    quote = normalize_quote(item.get("direct_quote"))
    return (
        (format_document_title(citation.get("document_name"), citation.get("document_type")) or "").lower(),
        (_clean(item.get("article_or_section") or citation.get("article_or_section")) or "").lower(),
        str(citation.get("page") if citation.get("page") is not None else "").lower(),
        quote,
    )


def authority_location_key(item: dict[str, Any]) -> tuple[str, ...]:
    citation = item.get("citation") or {}
    return (
        (format_document_title(citation.get("document_name"), citation.get("document_type")) or "").lower(),
        (_clean(item.get("article_or_section") or citation.get("article_or_section")) or "").lower(),
    )


def ranked_item_to_authority_card(item: dict[str, Any]) -> dict[str, Any]:
    citation = normalize_citation_pages(
        {
            "document_name": item.get("document_name"),
            "document_type": item.get("document_type"),
            "page": item.get("page"),
        }
    )
    return {
        "article_or_section": item.get("article_or_section") or "",
        "issue": item.get("legal_issue") or item.get("issue") or "",
        "role": item.get("role") or "",
        "role_title": format_role_label(item.get("role")),
        "why_relevant": item.get("why_relevant") or item.get("why_it_matters") or "",
        "direct_quotes": [item.get("direct_quote")] if _clean(item.get("direct_quote")) else [],
        "citation": citation,
        "citation_label": format_steward_citation(
            citation,
            article_or_section=item.get("article_or_section"),
        ),
    }
