"""Steward-facing text and label formatting for report export."""

from __future__ import annotations

import ast
import re
from typing import Any

from app.services.report_export.citation_formatter import (
    _clean,
    format_document_title,
    format_steward_citation,
)

_PLACEHOLDER_PATTERN = re.compile(
    r"\b(unknown|n/a|none|null|section unknown)\b",
    re.IGNORECASE,
)

EMBEDDED_QUOTE_MAX_LENGTH = 200
_DISPLAY_ELLIPSIS = "…"


def _resolve_full_quote(
    text: str,
    *,
    full_quote: str | None = None,
    known_quotes: list[str] | None = None,
) -> str | None:
    probe = text.rstrip(f". '\"{_DISPLAY_ELLIPSIS}").strip()
    if not probe:
        return None

    full = _clean(full_quote)
    if full and full.startswith(probe):
        return full

    for candidate in known_quotes or []:
        resolved = _clean(candidate)
        if resolved and resolved.startswith(probe):
            return resolved
    return full


def _truncate_at_word_boundary(text: str, max_length: int) -> tuple[str, bool]:
    if len(text) <= max_length:
        return text, False

    reserve = max_length - len(_DISPLAY_ELLIPSIS)
    if reserve <= 0:
        return _DISPLAY_ELLIPSIS, True

    excerpt = text[:reserve].rstrip()
    last_space = excerpt.rfind(" ")
    if last_space > 0:
        excerpt = excerpt[:last_space]
    excerpt = excerpt.rstrip(" .,;:\"'")
    return excerpt, True


def _append_display_ellipsis(text: str) -> str:
    cleaned = text.rstrip(f" .,;:\"'{_DISPLAY_ELLIPSIS}").rstrip()
    if not cleaned:
        return _DISPLAY_ELLIPSIS
    return f"{cleaned}{_DISPLAY_ELLIPSIS}"


_INTERNAL_PIPELINE_TERMS = (
    (r"\bremedy_support\b", "contractual remedy"),
    (r"\babove the relevance gates\.?", "in the indexed sources"),
    (r"\brelevance gates?\b", "source review"),
    (r"\branked chunks?\b", "retrieved sources"),
    (r"\bretrieval scores?\b", "source review"),
    (r"\bdecomposed issues?\b", "identified issues"),
    (r"\bmodel outputs?\b", "analysis"),
    (r"\bcoverage floors?\b", "source review"),
)


def format_display_quote(
    quote: str | None,
    *,
    full_quote: str | None = None,
    known_quotes: list[str] | None = None,
    max_length: int | None = None,
) -> str | None:
    """Ensure grounded quotes read as complete sentences or marked excerpts."""
    text = _clean(quote)
    if not text:
        return None

    resolved_full = _resolve_full_quote(
        text,
        full_quote=full_quote,
        known_quotes=known_quotes,
    )
    truncated = False
    if resolved_full:
        text = resolved_full
    elif max_length is not None and len(text) > max_length:
        text, truncated = _truncate_at_word_boundary(text, max_length)

    if re.search(r'[.!?]["\']?\s*$', text):
        return text
    if text.endswith(_DISPLAY_ELLIPSIS):
        return text
    if text.endswith("..."):
        return _append_display_ellipsis(text.rstrip("."))
    if truncated:
        return _append_display_ellipsis(text)
    return _append_display_ellipsis(text)


def sanitize_embedded_quotes_in_text(
    text: str,
    *,
    known_quotes: list[str] | None = None,
    max_length: int = EMBEDDED_QUOTE_MAX_LENGTH,
) -> str:
    """Fix truncated quotations embedded in narrative text."""

    def _replace(match: re.Match[str]) -> str:
        quoted = match.group(1)
        formatted = format_display_quote(
            quoted,
            known_quotes=known_quotes,
            max_length=max_length,
        ) or quoted
        return f'"{formatted}"'

    return re.sub(r'"([^"]+)"', _replace, text)


def dedupe_public_citation_labels(labels: list[str]) -> list[str]:
    seen: set[str] = set()
    deduped: list[str] = []
    for label in labels:
        key = re.sub(r"\s+", " ", label.strip().lower())
        if not key or key in seen:
            continue
        seen.add(key)
        deduped.append(label.strip())
    return deduped


def dedupe_authority_items(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    deduped: list[dict[str, Any]] = []
    for item in items:
        label = format_cited_authority_label(item).lower()
        if label in seen:
            continue
        seen.add(label)
        deduped.append(item)
    return deduped


def _issue_semantic_key(text: str) -> str:
    normalized = re.sub(r"\s+", " ", text.lower().strip())
    normalized = re.sub(r"[^\w\s]", "", normalized)
    normalized = re.sub(r"\b(previously approved|pre approved|preapproved|previously)\b", "approved", normalized)
    normalized = re.sub(r"\bapproved approved\b", "approved", normalized)
    return re.sub(r"\s+", " ", normalized).strip()


def _issue_compare_key(text: str) -> str:
    return re.sub(r"[^\w\s]", "", text.lower())


def _issues_semantically_equivalent(left: str, right: str) -> bool:
    left_key = _issue_semantic_key(left)
    right_key = _issue_semantic_key(right)
    if not left_key or not right_key:
        return False
    if left_key == right_key:
        return True
    left_raw = _issue_compare_key(left)
    right_raw = _issue_compare_key(right)
    if left_raw in right_raw or right_raw in left_raw:
        return True
    if left_key in right_key or right_key in left_key:
        if "cancel" in left_key and "cancel" in right_key:
            return True
    return False


def _normalize_sentence_key(text: str) -> str:
    cleaned = sanitize_public_text(text).lower().strip(" .")
    cleaned = re.sub(r"\bmanagement management\b", "management", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned)
    return cleaned


def _append_unique_sentence(parts: list[str], candidate: str) -> None:
    candidate = candidate.strip()
    if not candidate:
        return
    candidate_key = _normalize_sentence_key(candidate)
    for existing in parts:
        existing_key = _normalize_sentence_key(existing)
        if candidate_key == existing_key:
            return
        if candidate_key in existing_key or existing_key in candidate_key:
            return
    parts.append(candidate.rstrip("."))


def _strip_embedded_authority_clauses(summary: str) -> str:
    cleaned = summary.strip()
    marker = "Retrieved authorities include:"
    lowered = cleaned.lower()
    marker_index = lowered.find(marker.lower())
    if marker_index >= 0:
        prefix = cleaned[:marker_index].strip()
        suffix = cleaned[marker_index + len(marker) :]
        end_period = suffix.rfind(".")
        remainder = suffix[end_period + 1 :].strip() if end_period >= 0 else ""
        cleaned = prefix
        if remainder:
            cleaned = f"{prefix} {remainder}".strip()

    cleaned = re.sub(r"\.\d+\s*\([^)]*\)", "", cleaned)
    cleaned = re.sub(r"(?:^|\s)\d+\);\s*", " ", cleaned)
    cleaned = re.sub(r"\s*\(\s*[^)]*\);\s*", " ", cleaned)
    cleaned = re.sub(r"\s{2,}", " ", cleaned)
    cleaned = re.sub(r"\.\s*\.", ".", cleaned)
    return cleaned.strip(" ;,")


def extract_management_supporting_facts(report: dict[str, Any]) -> list[str]:
    """Return dedicated management-position facts only when explicitly structured."""
    candidates: list[Any] = []
    for key in ("management_supporting_facts", "management_position_facts", "management_position"):
        value = report.get(key)
        if value:
            candidates.append(value)
    analysis = report.get("detailed_analysis") or {}
    for key in ("management_supporting_facts", "management_position_facts", "management_position"):
        value = analysis.get(key)
        if value:
            candidates.append(value)

    facts: list[str] = []
    for candidate in candidates:
        if isinstance(candidate, str) and _clean(candidate):
            facts.append(candidate)
        elif isinstance(candidate, list):
            for item in candidate:
                if isinstance(item, str) and _clean(item):
                    facts.append(item)
                elif isinstance(item, dict):
                    text = _clean(item.get("fact") or item.get("text") or item.get("statement"))
                    if text:
                        facts.append(text)
    return dedupe_public_citation_labels(facts)


def collect_grounded_quotes_from_report(
    raw: dict[str, Any],
    report: dict[str, Any],
) -> list[str]:
    quotes: list[str] = []
    seen: set[str] = set()

    def _add(value: Any) -> None:
        cleaned = _clean(value)
        if not cleaned:
            return
        key = cleaned.lower()
        if key in seen:
            return
        seen.add(key)
        quotes.append(cleaned)

    for item in raw.get("ranked_authorities") or []:
        _add(item.get("direct_quote"))

    sections = (
        "key_contract_violations",
        "union_supporting_authority",
        "procedural_requirements",
        "information_rights",
        "timeline_requirements",
        "remedy_authority",
        "background_authority",
        "management_limiting_authority",
        "supporting_evidence",
    )
    for section in sections:
        for item in report.get(section) or []:
            _add(item.get("direct_quote"))
    return quotes


def format_strategic_tips_display(
    tips: list[dict[str, Any]],
    *,
    known_quotes: list[str] | None = None,
) -> list[dict[str, str]]:
    formatted: list[dict[str, str]] = []
    for tip in tips or []:
        title = _clean(tip.get("title")) or ""
        text = sanitize_embedded_quotes_in_text(
            sanitize_public_text(tip.get("text") or ""),
            known_quotes=known_quotes,
        )
        if title or text:
            formatted.append({"title": title, "text": text})
    return formatted


def normalize_article_section_label(text: str | None) -> str | None:
    """Normalize article/section labels and remove redundant duplication."""
    raw = _clean(text)
    if not raw:
        return None

    article_match = re.search(r"article\s+([\d.]+)", raw, re.IGNORECASE)
    section_match = re.search(r"section\s+([\d.]+)", raw, re.IGNORECASE)
    article_num = article_match.group(1) if article_match else None
    section_num = section_match.group(1) if section_match else None

    if article_num and section_num:
        if article_num == section_num:
            return f"Article {article_num}"
        return f"Article {article_num}, Section {section_num}"

    if article_num:
        return f"Article {article_num}"
    if section_num:
        return f"Section {section_num}"

    if _PLACEHOLDER_PATTERN.search(raw):
        return None
    return raw


def format_authority_heading(item: dict[str, Any]) -> str:
    """Public heading for authority cards and violation blocks."""
    article = normalize_article_section_label(item.get("article_or_section"))
    if article:
        return article

    citation = item.get("citation") or {}
    fallback = format_steward_citation(
        citation,
        article_or_section=None,
    )
    if fallback:
        return fallback

    document = format_document_title(
        citation.get("document_name") or item.get("document_name"),
        citation.get("document_type") or item.get("document_type"),
    )
    if document:
        return document
    return "Governing Authority"


def format_cited_authority_label(item: dict[str, Any]) -> str:
    """Compact authority label for Quick Assessment lists."""
    article = normalize_article_section_label(item.get("article_or_section"))
    citation = item.get("citation") or {}
    document = format_document_title(
        citation.get("document_name") or item.get("document_name"),
        citation.get("document_type") or item.get("document_type"),
    )
    page = citation.get("page") if citation.get("page") is not None else item.get("page")
    page_part = f", p. {page}" if page is not None else ""

    if article and document:
        return f"{article} ({document}{page_part})"
    if document:
        return f"{document}{page_part}" if page_part else document
    if article:
        return article
    return "Governing authority"


def _parse_dispute_frame_value(frame: Any) -> dict[str, Any] | None:
    if isinstance(frame, dict):
        return frame
    if not isinstance(frame, str):
        return None
    text = frame.strip()
    if not text:
        return None
    if text.startswith("{") and "actor" in text:
        try:
            parsed = ast.literal_eval(text)
            if isinstance(parsed, dict):
                return parsed
        except (SyntaxError, ValueError):
            pass
    return None


def format_dispute_frame_sentence(frame: Any) -> str | None:
    """Convert structured dispute-frame data into steward-facing prose."""
    parsed = _parse_dispute_frame_value(frame)
    if parsed:
        actor = (_clean(parsed.get("actor")) or "").lower()
        action = _clean(parsed.get("action"))
        management_actions = [
            _clean(value) for value in (parsed.get("management_actions") or []) if _clean(value)
        ]
        employee_actions = [
            _clean(value) for value in (parsed.get("employee_actions") or []) if _clean(value)
        ]

        sentences: list[str] = []
        if action:
            action_clean = action.rstrip(".")
            action_lower = action_clean.lower()
            if actor == "management":
                if action_lower.startswith("management"):
                    sentences.append(f"{action_clean}.")
                elif action_clean and action_clean[0].isupper():
                    sentences.append(
                        f"The dispute involves {action_clean[0].lower()}{action_clean[1:]}."
                    )
                else:
                    action_text = action_clean[0].lower() + action_clean[1:] if action_clean else action_clean
                    sentences.append(f"Management {action_text}.")
            elif actor and not action_lower.startswith(actor):
                sentences.append(f"{actor.capitalize()} {action_clean}.")
            else:
                sentences.append(f"{action_clean}.")
        elif management_actions:
            sentences.append("; ".join(management_actions).rstrip(".") + ".")
        elif employee_actions:
            sentences.append("; ".join(employee_actions).rstrip(".") + ".")

        return " ".join(sentences) if sentences else None

    text = _clean(frame if isinstance(frame, str) else None)
    if not text:
        return None
    if text.startswith("{") and "'actor'" in text:
        reparsed = _parse_dispute_frame_value(text)
        if reparsed:
            return format_dispute_frame_sentence(reparsed)
        return None
    return text


def sanitize_public_text(text: str | None) -> str:
    """Remove internal pipeline terminology and awkward punctuation from public text."""
    if not text:
        return ""

    cleaned = str(text).strip()
    if re.search(
        r"No remedy_support authority was retrieved above the relevance gates",
        cleaned,
        re.IGNORECASE,
    ):
        confirm_match = re.search(r"(Confirm:.*)$", cleaned, re.IGNORECASE | re.DOTALL)
        confirm_suffix = ""
        if confirm_match:
            confirm_suffix = " " + sanitize_public_text(confirm_match.group(1))
        cleaned = (
            "No sufficiently relevant contractual remedy authority was located. "
            "Confirm the applicable remedy language before requesting make-whole or other relief."
            + confirm_suffix
        )

    for pattern, replacement in _INTERNAL_PIPELINE_TERMS:
        cleaned = re.sub(pattern, replacement, cleaned, flags=re.IGNORECASE)

    cleaned = re.sub(r"\.{2,}", ".", cleaned)
    cleaned = re.sub(r"\s+\.", ".", cleaned)
    cleaned = re.sub(r"\s{2,}", " ", cleaned)
    return cleaned.strip()


def _strip_internal_prefixes(text: str) -> str:
    cleaned = text.strip()
    for prefix in ("Dispute frame:", "Primary legal issue identified from authorities:"):
        if cleaned.startswith(prefix):
            cleaned = cleaned[len(prefix) :].strip()
    return cleaned


def format_grievance_framework_display(
    raw_framework: str | None,
    issue_analysis: dict[str, Any] | None,
    key_violations: list[dict[str, Any]],
) -> str:
    """Render Detailed Analysis issue statement without raw structured payloads."""
    issue_analysis = issue_analysis or {}
    parts: list[str] = []

    dispute_sentence = format_dispute_frame_sentence(issue_analysis.get("dispute_frame"))
    if not dispute_sentence and raw_framework:
        raw = _strip_internal_prefixes(raw_framework)
        dispute_sentence = format_dispute_frame_sentence(raw)
        if not dispute_sentence and raw and not raw.startswith("{"):
            dispute_sentence = sanitize_public_text(raw)

    if dispute_sentence:
        _append_unique_sentence(parts, dispute_sentence)

    primary = _clean(issue_analysis.get("primary_issue"))
    if primary:
        _append_unique_sentence(parts, primary)

    violation_bits: list[str] = []
    seen_violation_bits: set[str] = set()
    for item in key_violations:
        heading = format_authority_heading(item)
        issue = _clean(item.get("issue") or item.get("why_relevant"))
        if heading and issue and heading.lower() not in {"governing authority", "governing authority."}:
            bit = f"{heading}: {issue.rstrip('.')}"
            bit_key = bit.lower()
            if bit_key in seen_violation_bits:
                continue
            seen_violation_bits.add(bit_key)
            violation_bits.append(bit)

    if violation_bits:
        parts.append(
            "Contract provisions flagged for review: "
            + "; ".join(violation_bits[:6])
        )

    if not parts:
        return ""

    sentence = ". ".join(part.rstrip(".") for part in parts if part.strip()) + "."
    return sanitize_public_text(sentence)


def sanitize_cited_authority_strings(labels: list[str]) -> list[str]:
    """Best-effort cleanup for legacy cited-authority strings stored in report JSON."""
    sanitized: list[str] = []
    for label in labels or []:
        text = sanitize_public_text(str(label))
        text = re.sub(
            r"^(Unknown|N/A|None)\s*\(",
            "(",
            text,
            flags=re.IGNORECASE,
        )
        text = re.sub(
            r"Article\s+([\d.]+)\s+Section\s+\1",
            r"Article \1",
            text,
            flags=re.IGNORECASE,
        )
        text = re.sub(r"\(\s*,", "(", text)
        text = text.replace("()", "").strip(" ;,")
        if text and not _PLACEHOLDER_PATTERN.fullmatch(text):
            sanitized.append(text)
    return sanitized


def rebuild_quick_assessment_display(
    quick_assessment: dict[str, Any],
    authority_items: list[dict[str, Any]],
) -> dict[str, Any]:
    """Sanitize Quick Assessment fields for steward-facing export."""
    deduped_items = dedupe_authority_items(authority_items)
    cited_labels = dedupe_public_citation_labels(
        [format_cited_authority_label(item) for item in deduped_items[:6]]
    )
    if not cited_labels:
        cited_labels = dedupe_public_citation_labels(
            sanitize_cited_authority_strings(quick_assessment.get("cited_authorities") or [])
        )

    summary = sanitize_public_text(quick_assessment.get("summary") or "")
    summary = _strip_embedded_authority_clauses(summary)
    summary = re.sub(
        r"Article\s+([\d.]+)\s+Section\s+\1",
        r"Article \1",
        summary,
        flags=re.IGNORECASE,
    )
    summary = re.sub(
        r"Unknown\s*\(",
        "(",
        summary,
        flags=re.IGNORECASE,
    )
    summary = sanitize_public_text(summary)

    return {
        "summary": summary,
        "grievability": quick_assessment.get("grievability") or "",
        "confidence": quick_assessment.get("confidence") or "",
        "why": sanitize_public_text(quick_assessment.get("why") or ""),
        "cited_authorities": cited_labels,
    }


def format_recommended_remedy_display(remedy: dict[str, Any]) -> dict[str, Any]:
    statements = [
        sanitize_public_text(statement)
        for statement in (remedy.get("statements") or [])
        if sanitize_public_text(statement)
    ]
    insufficient = sanitize_public_text(remedy.get("insufficient_notice"))
    return {
        "statements": statements,
        "insufficient_notice": insufficient or None,
    }


def build_issues_presented(raw: dict[str, Any], report: dict[str, Any]) -> list[str]:
    issue_analysis = raw.get("issue_analysis") or report.get("issue_analysis") or {}
    issues: list[str] = []

    primary = _clean(issue_analysis.get("primary_issue"))
    if primary:
        issues.append(primary)

    for secondary in report.get("secondary_issues") or []:
        cleaned = _clean(secondary)
        if not cleaned:
            continue
        if any(_issues_semantically_equivalent(cleaned, existing) for existing in issues):
            continue
        issues.append(cleaned)
    return issues


def _disclosure_meaning_key(text: str) -> str | None:
    normalized = re.sub(r"\s+", " ", str(text).strip().lower())
    if "lmou" in normalized and "not currently indexed" in normalized:
        return "lmou_unindexed"
    if "local memorandum" in normalized and "not currently indexed" in normalized:
        return "lmou_unindexed"
    return None


def dedupe_semantic_disclosures(limitations: dict[str, Any]) -> dict[str, Any]:
    """Remove caveat text that repeats structured unindexed-source disclosures."""
    limitations = dict(limitations)
    gaps = dict(limitations.get("retrieval_gaps") or {})
    unindexed = gaps.get("unindexed_sources_requested") or []
    has_lmou_panel = any(str(source).upper() == "LMOU" for source in unindexed)

    if not has_lmou_panel:
        return limitations

    filtered_caveats: list[str] = []
    for caveat in limitations.get("caveats") or []:
        if _disclosure_meaning_key(caveat) == "lmou_unindexed":
            continue
        filtered_caveats.append(caveat)
    limitations["caveats"] = filtered_caveats
    limitations["retrieval_gaps"] = gaps
    return limitations
