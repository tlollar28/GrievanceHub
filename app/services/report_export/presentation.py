"""Prepare steward-facing presentation data for report export."""

from __future__ import annotations

import re
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

from app.services.report_export.citation_formatter import (
    authority_identity_key,
    authority_location_key,
    collect_page_numbers,
    format_document_title,
    format_role_label,
    format_source_reference_summary,
    format_steward_citation,
    normalize_citation_pages,
    normalize_quote,
    ranked_item_to_authority_card,
    _clean,
)
from app.services.report_export.text_formatter import (
    build_issues_presented,
    collect_grounded_quotes_from_report,
    dedupe_semantic_disclosures,
    extract_management_supporting_facts,
    format_authority_heading,
    format_display_quote,
    format_grievance_framework_display,
    format_recommended_remedy_display,
    format_strategic_tips_display,
    rebuild_quick_assessment_display,
)

_MANAGEMENT_ROLES = frozenset({"management_limiting", "management_limiting_authority"})
_AUTHORITY_REPORT_SECTIONS = (
    "key_contract_violations",
    "union_supporting_authority",
    "procedural_requirements",
    "information_rights",
    "timeline_requirements",
    "remedy_authority",
    "background_authority",
)
_TEMPLATE_PLACEHOLDER_MARKERS = (
    "not yet available",
    "template matching is not",
)


def format_generated_at(value: Any, *, timezone_name: str = "America/New_York") -> str | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        dt = value
    else:
        text = str(value).strip()
        if not text:
            return None
        normalized = text.replace("Z", "+00:00")
        try:
            dt = datetime.fromisoformat(normalized)
        except ValueError:
            return text
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=ZoneInfo("UTC"))
    local = dt.astimezone(ZoneInfo(timezone_name))
    formatted = local.strftime("%B %d, %Y at %I:%M %p")
    formatted = re.sub(r" 0(\d),", r" \1,", formatted)
    formatted = re.sub(r" at 0(\d):", r" at \1:", formatted)
    tz_abbr = local.tzname() or timezone_name
    return f"{formatted} {tz_abbr}"


def format_case_reference(case_uuid: str | None) -> str | None:
    if not case_uuid:
        return None
    text = str(case_uuid).strip()
    if not text:
        return None
    short = text.split("-")[0].upper()
    return f"Case Ref: {short}"


def _report_item_to_card(item: dict[str, Any]) -> dict[str, Any]:
    citation = normalize_citation_pages(item.get("citation") or {})
    quote = item.get("direct_quote")
    card = {
        "article_or_section": item.get("article_or_section") or "",
        "issue": item.get("issue") or "",
        "role": item.get("role") or "",
        "role_title": format_role_label(item.get("role"), item.get("role_title")),
        "why_relevant": item.get("why_relevant") or "",
        "direct_quotes": [quote] if quote and str(quote).strip() else [],
        "citation": citation,
        "citation_label": format_steward_citation(
            citation,
            article_or_section=item.get("article_or_section"),
        ),
    }
    card["heading_label"] = format_authority_heading(card)
    return card


def _refresh_card_citation(card: dict[str, Any]) -> dict[str, Any]:
    citation = normalize_citation_pages(card.get("citation") or {})
    updated = {**card, "citation": citation}
    updated["citation_label"] = format_steward_citation(
        citation,
        article_or_section=updated.get("article_or_section"),
    )
    return updated


def _merge_card_citation_pages(left: dict[str, Any], right: dict[str, Any]) -> dict[str, Any]:
    merged_pages = collect_page_numbers(
        (left.get("citation") or {}).get("pages"),
        (left.get("citation") or {}).get("page"),
        (right.get("citation") or {}).get("pages"),
        (right.get("citation") or {}).get("page"),
    )
    citation = normalize_citation_pages(
        {
            **(left.get("citation") or {}),
            **(right.get("citation") or {}),
            "pages": merged_pages,
            "page": merged_pages[0] if merged_pages else (left.get("citation") or {}).get("page"),
        }
    )
    return _refresh_card_citation({**left, "citation": citation})


def _merge_authority_cards(cards: list[dict[str, Any]]) -> list[dict[str, Any]]:
    merged: list[dict[str, Any]] = []
    index_by_location: dict[tuple[str, ...], int] = {}

    for card in cards:
        location_key = authority_location_key(card)
        quote = normalize_quote((card.get("direct_quotes") or [""])[0])
        if location_key in index_by_location:
            existing = merged[index_by_location[location_key]]
            existing_quotes = {normalize_quote(q) for q in existing.get("direct_quotes") or []}
            for raw_quote in card.get("direct_quotes") or []:
                normalized = normalize_quote(raw_quote)
                if normalized and normalized not in existing_quotes:
                    existing["direct_quotes"].append(raw_quote)
                    existing_quotes.add(normalized)
            if not existing.get("why_relevant") and card.get("why_relevant"):
                existing["why_relevant"] = card["why_relevant"]
            if not existing.get("issue") and card.get("issue"):
                existing["issue"] = card["issue"]
            merged[index_by_location[location_key]] = _merge_card_citation_pages(existing, card)
            continue

        index_by_location[location_key] = len(merged)
        merged.append(_refresh_card_citation({**card, "direct_quotes": list(card.get("direct_quotes") or [])}))
        _ = quote

    return merged


def build_top_governing_authorities(
    raw: dict[str, Any],
    report: dict[str, Any],
    *,
    max_items: int = 5,
) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    ranked = raw.get("ranked_authorities") or []
    if ranked:
        for item in ranked:
            role = (item.get("role") or "").strip()
            if role in _MANAGEMENT_ROLES:
                continue
            candidates.append(ranked_item_to_authority_card(item))
    else:
        for section in _AUTHORITY_REPORT_SECTIONS:
            for item in report.get(section) or []:
                role = (item.get("role") or "").strip()
                if role in _MANAGEMENT_ROLES:
                    continue
                candidates.append(_report_item_to_card(item))

    merged = _merge_authority_cards(candidates)
    seen_identities: set[tuple[str, ...]] = set()
    selected: list[dict[str, Any]] = []

    for card in merged:
        quotes = card.get("direct_quotes") or []
        primary_quote = quotes[0] if quotes else ""
        identity = authority_identity_key(
            {
                "article_or_section": card.get("article_or_section"),
                "direct_quote": primary_quote,
                "citation": card.get("citation") or {},
            }
        )
        if identity in seen_identities:
            continue
        seen_identities.add(identity)
        selected.append({**card, "heading_label": format_authority_heading(card)})
        if len(selected) >= max_items:
            break

    return selected


def collect_full_quotes(cards: list[dict[str, Any]]) -> set[str]:
    quotes: set[str] = set()
    for card in cards:
        for quote in card.get("direct_quotes") or []:
            normalized = normalize_quote(quote)
            if normalized:
                quotes.add(normalized)
    return quotes


def suppress_quote(item: dict[str, Any], displayed_quotes: set[str]) -> dict[str, Any]:
    quote = item.get("direct_quote")
    normalized = normalize_quote(quote)
    if normalized and normalized in displayed_quotes:
        return {**item, "direct_quote": None, "quote_suppressed": True}
    return item


def is_factual_evidence_item(item: dict[str, Any]) -> bool:
    doc_type = (item.get("document_type") or "").upper()
    if doc_type in {"CONTRACT", "CIM", "ELM", "LMOU"}:
        return False
    supports = (item.get("what_it_supports") or "").lower()
    factual_markers = (
        "notice",
        "schedule",
        "leave slip",
        "clock ring",
        "payroll",
        "witness",
        "information request",
        "management response",
        "letter",
        "email",
        "document",
        "record",
        "approval",
        "cancellation",
    )
    return any(marker in supports for marker in factual_markers)


def filter_supporting_evidence(
    items: list[dict[str, Any]],
    displayed_quotes: set[str],
) -> list[dict[str, Any]]:
    filtered: list[dict[str, Any]] = []
    for item in items or []:
        quote = normalize_quote(item.get("direct_quote"))
        if quote and quote in displayed_quotes:
            continue
        if not is_factual_evidence_item(item) and quote:
            continue
        cleaned = {
            **item,
            "citation_label": format_steward_citation(
                {
                    "document_name": item.get("document_name"),
                    "document_type": item.get("document_type"),
                    "page": item.get("page"),
                },
                article_or_section=item.get("article_or_section"),
            ),
        }
        if quote and not is_factual_evidence_item(item):
            cleaned["direct_quote"] = None
        filtered.append(cleaned)
    return filtered


def dedupe_limitation_texts(texts: list[str]) -> list[str]:
    seen: set[str] = set()
    deduped: list[str] = []
    for text in texts or []:
        normalized = re.sub(r"\s+", " ", str(text).strip().lower())
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        deduped.append(str(text).strip())
    return deduped


def prepare_limitations(report: dict[str, Any]) -> dict[str, Any]:
    limitations = dict(report.get("limitations") or {})
    gaps = dict(limitations.get("retrieval_gaps") or {})
    limitations["caveats"] = dedupe_limitation_texts(limitations.get("caveats") or [])

    unindexed = dedupe_limitation_texts(gaps.get("unindexed_sources_requested") or [])
    unavailable = dedupe_limitation_texts(
        [
            str(topic).replace("_", " ")
            for topic in (gaps.get("authority_topics_unavailable_in_index") or [])
        ]
    )
    gaps["unindexed_sources_requested"] = unindexed
    gaps["authority_topics_unavailable_in_index"] = unavailable
    limitations["retrieval_gaps"] = gaps
    return limitations


def has_real_templates(report: dict[str, Any]) -> bool:
    templates = report.get("matching_grievance_templates") or []
    return bool(templates)


def should_show_templates_notice(report: dict[str, Any]) -> bool:
    if has_real_templates(report):
        return True
    notice = (report.get("matching_grievance_templates_notice") or "").strip()
    if not notice:
        return False
    lowered = notice.lower()
    return not any(marker in lowered for marker in _TEMPLATE_PLACEHOLDER_MARKERS)


def authority_count_label(count: int) -> str:
    label = "authority" if count == 1 else "authorities"
    return f"{count} {label}"


def _collect_ranked_passage_records(raw: dict[str, Any], report: dict[str, Any]) -> list[dict[str, Any]]:
    ranked = raw.get("ranked_authorities") or []
    if ranked:
        return [item for item in ranked if str(item.get("document_type") or "").strip()]

    records: list[dict[str, Any]] = []
    for section in _AUTHORITY_REPORT_SECTIONS + ("management_limiting_authority",):
        for item in report.get(section) or []:
            citation = item.get("citation") or {}
            records.append(
                {
                    "document_name": citation.get("document_name") or item.get("document_name"),
                    "document_type": citation.get("document_type") or item.get("document_type"),
                    "article_or_section": item.get("article_or_section"),
                    "page": citation.get("page") if citation.get("page") is not None else item.get("page"),
                }
            )
    return records


def build_source_references_display(raw: dict[str, Any], report: dict[str, Any]) -> dict[str, Any]:
    refs = dict(report.get("source_references") or {})
    not_found = list(refs.get("not_found") or [])

    buckets: dict[str, dict[str, Any]] = {}
    for item in _collect_ranked_passage_records(raw, report):
        source_type = str(item.get("document_type") or "").upper()
        if not source_type:
            continue
        bucket = buckets.setdefault(
            source_type,
            {
                "source_type": source_type,
                "document_names": set(),
                "location_keys": set(),
                "passage_count": 0,
            },
        )
        document_name = format_document_title(item.get("document_name"), source_type)
        if document_name:
            bucket["document_names"].add(document_name)
        bucket["passage_count"] += 1
        bucket["location_keys"].add(
            authority_location_key(
                {
                    "article_or_section": item.get("article_or_section"),
                    "citation": {
                        "document_name": item.get("document_name"),
                        "document_type": source_type,
                    },
                }
            )
        )

    found: list[dict[str, Any]] = []
    for source_type in sorted(buckets.keys()):
        bucket = buckets[source_type]
        distinct_count = len(bucket["location_keys"])
        passage_count = bucket["passage_count"]
        found.append(
            {
                "source_type": source_type,
                "document_names": sorted(bucket["document_names"]),
                "distinct_authority_count": distinct_count,
                "passage_count": passage_count,
                "summary_label": format_source_reference_summary(distinct_count, passage_count),
            }
        )

    return {"found": found, "not_found": not_found}


def _enrich_authority_item(item: dict[str, Any]) -> dict[str, Any]:
    citation = item.get("citation") or {}
    direct_quote = format_display_quote(item.get("direct_quote"))
    enriched = {
        **item,
        "direct_quote": direct_quote,
        "citation_label": format_steward_citation(
            citation,
            article_or_section=item.get("article_or_section"),
        ),
    }
    enriched["heading_label"] = format_authority_heading(enriched)
    return enriched


def _enrich_top_authority_card(card: dict[str, Any]) -> dict[str, Any]:
    quotes = [
        formatted
        for formatted in (
            format_display_quote(quote) for quote in (card.get("direct_quotes") or [])
        )
        if formatted
    ]
    return {
        **card,
        "direct_quotes": quotes,
        "heading_label": card.get("heading_label") or format_authority_heading(card),
    }


def prepare_presentation(
    raw: dict[str, Any],
    report: dict[str, Any],
    *,
    case_uuid: str | None = None,
    version_number: int | None = None,
) -> dict[str, Any]:
    top_authorities = [
        _enrich_top_authority_card({**card, "heading_label": format_authority_heading(card)})
        for card in build_top_governing_authorities(raw, report)
    ]
    displayed_quotes = collect_full_quotes(top_authorities)

    key_violations = [
        suppress_quote(item, displayed_quotes)
        for item in (report.get("key_contract_violations") or [])
    ]
    key_violations = [_enrich_authority_item(item) for item in key_violations]

    management_items = [
        _enrich_authority_item(item)
        for item in (report.get("management_limiting_authority") or [])
    ]
    report = {**report, "management_limiting_authority": management_items}

    supporting_evidence = filter_supporting_evidence(
        report.get("supporting_evidence") or [],
        displayed_quotes,
    )

    limitations = dedupe_semantic_disclosures(prepare_limitations(report))
    source_summary = dict(report.get("source_summary") or {})
    authority_count = len(top_authorities)

    authority_items_for_qa = top_authorities + key_violations
    quick_assessment_display = rebuild_quick_assessment_display(
        report.get("quick_assessment") or {},
        authority_items_for_qa,
    )
    recommended_remedy_display = format_recommended_remedy_display(
        report.get("recommended_remedy") or {},
    )
    issues_presented = build_issues_presented(raw, report)
    grievance_framework_display = format_grievance_framework_display(
        (report.get("detailed_analysis") or {}).get("grievance_framework"),
        raw.get("issue_analysis") or report.get("issue_analysis"),
        key_violations,
    )
    management_supporting_facts = extract_management_supporting_facts(report)
    grounded_quotes = collect_grounded_quotes_from_report(raw, report)
    strategic_tips_display = format_strategic_tips_display(
        (report.get("detailed_analysis") or {}).get("strategic_tips") or [],
        known_quotes=grounded_quotes,
    )

    generated_at_raw = report.get("generated_at") or raw.get("generated_at")
    return {
        "top_governing_authorities": top_authorities,
        "key_contract_violations": key_violations,
        "management_limiting_authority": management_items,
        "supporting_evidence": supporting_evidence,
        "limitations": limitations,
        "generated_at_display": format_generated_at(generated_at_raw),
        "generated_at_raw": generated_at_raw,
        "case_reference": format_case_reference(case_uuid or (report.get("case_information") or {}).get("case_id")),
        "authority_count_label": authority_count_label(authority_count),
        "source_references_display": build_source_references_display(raw, report),
        "show_templates_section": has_real_templates(report),
        "known_facts": limitations.get("known_facts") or [],
        "missing_facts": limitations.get("missing_facts") or [],
        "quick_assessment": quick_assessment_display,
        "recommended_remedy": recommended_remedy_display,
        "issues_presented": issues_presented,
        "grievance_framework_display": grievance_framework_display,
        "management_supporting_facts": management_supporting_facts,
        "strategic_tips": strategic_tips_display,
        "primary_issue_available": bool(
            _clean((raw.get("issue_analysis") or report.get("issue_analysis") or {}).get("primary_issue"))
        ),
    }
