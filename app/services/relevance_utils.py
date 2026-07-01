import re
from dataclasses import dataclass, field
from typing import Any

from app.retrieval_config import (
    BOILERPLATE_PENALTY,
    DEFAULT_SOURCE_WEIGHT,
    DIRECTION_CONTRADICTION_PENALTY,
    EMBEDDING_FALLBACK_THRESHOLD,
    EMBEDDING_SCORE_WEIGHT,
    KEYWORD_SCORE_WEIGHT,
    MAX_CHUNKS_PER_ISSUE,
    MIN_CHUNKS_PER_ISSUE,
    MIN_COMBINED_RETRIEVAL_SCORE,
    MIN_EMBEDDING_SIMILARITY,
    PROCEDURAL_ONLY_PENALTY,
    SOURCE_TYPE_WEIGHTS,
    SUBSTANTIVE_RULE_BONUS,
)

STOPWORDS = {
    "a", "an", "and", "are", "as", "at", "be", "been", "by", "can",
    "did", "do", "does", "for", "from", "has", "have", "he", "her",
    "his", "how", "i", "if", "in", "is", "it", "its", "me", "my",
    "not", "of", "on", "or", "our", "she", "should", "that", "the",
    "their", "them", "then", "there", "they", "this", "to", "under",
    "was", "we", "were", "what", "when", "where", "which", "who",
    "why", "will", "with", "without", "you", "your",
}

BOILERPLATE_PATTERNS = [
    "table of contents",
    "contents",
    "index",
    "page intentionally left blank",
    "list of articles",
    "article 1 union recognition",
    "article 2 non-discrimination",
    "itables of contents",
]

PROCEDURAL_SIGNAL_TERMS = [
    "article",
    "section",
    "memorandum",
    "mou",
    "elm",
    "grievance",
    "arbitration",
    "just cause",
    "information request",
    "union representative",
    "steward",
    "shall",
    "must",
    "may",
    "right",
    "rights",
    "violation",
    "remedy",
    "probationary",
]

ISSUE_TYPE_FIELDS = [
    ("legal_issues", "legal"),
    ("remedial_issues", "remedy"),
    ("timeline_issues", "timeline"),
    ("information_rights_issues", "information_rights"),
    ("local_agreement_issues", "local_agreement"),
]

# General retrieval templates keyed by issue_type (not question-specific).
ISSUE_TYPE_BACKFILL_TEMPLATES: dict[str, list[str]] = {
    "legal": [
        "governing contract rule employee rights union grievance",
        "contract obligation management action bargaining unit",
    ],
    "remedy": [
        "grievance remedy make whole rescind reinstatement",
        "appropriate remedy contract violation",
    ],
    "timeline": [
        "grievance filing deadline time limit days",
        "grievance procedure timeline notice period",
    ],
    "information_rights": [
        "union right to information records documents",
        "employer furnish information written union request",
    ],
    "local_agreement": [
        "local memorandum understanding provision",
    ],
}

MANAGEMENT_ACTION_TERMS = {
    "management",
    "supervisor",
    "employer",
    "postal",
    "service",
    "denied",
    "deny",
    "cancel",
    "cancelled",
    "canceled",
    "revoke",
    "revoked",
    "discipline",
    "disciplined",
    "assign",
    "assigned",
    "direct",
    "directed",
    "require",
    "required",
    "suspend",
    "suspended",
    "terminate",
    "terminated",
    "remove",
    "removed",
    "refuse",
    "refused",
    "fail",
    "failed",
}

EMPLOYEE_ACTION_TERMS = {
    "employee",
    "grievant",
    "request",
    "requested",
    "filed",
    "file",
    "report",
    "reported",
    "absent",
    "leave",
    "worked",
    "refused",
    "declined",
    "appeal",
    "appealed",
    "steward",
    "union",
}

SUBSTANTIVE_SIGNALS = [
    "shall",
    "must",
    "entitled",
    "entitle",
    "prohibited",
    "may not",
    "shall not",
    "will not",
    "required",
    "obligation",
    "right to",
    "rights",
    "just cause",
    "make whole",
    "reimburse",
    "compensat",
]

PROCEDURAL_ONLY_SIGNALS = [
    "file a grievance",
    "grievance procedure",
    "step 1",
    "step 2",
    "step 3",
    "within",
    "days of",
    "business days",
    "time limit",
    "deadline",
    "appeal",
    "arbitration",
    "informal discussion",
    "written grievance",
]

GENERIC_TOPIC_TERMS = {
    "leave",
    "overtime",
    "holiday",
    "pay",
    "schedule",
    "discipline",
    "seniority",
    "grievance",
    "employee",
    "management",
    "annual",
    "sick",
    "contract",
    "manual",
    "local",
}



DIRECTION_GENERIC_TOKENS = GENERIC_TOPIC_TERMS | {
    "employee",
    "management",
    "union",
    "previously",
    "without",
    "explanation",
    "notice",
    "handler",
    "mail",
    "regular",
    "approved",
    "annual",
    "writing",
    "request",
    "information",
    "grievant",
    "supervisor",
    "employer",
    "postal",
    "service",
    "steward",
    "assist",
    "assistance",
    "representation",
    "operational",
    "citing",
    "need",
    "filed",
    "file",
    "report",
    "reported",
    "appeal",
    "appealed",
}


@dataclass
class RetrievedChunk:
    chunk: Any
    best_embedding_distance: float = 1.0
    matched_query_count: int = 0
    keyword_overlap: float = 0.0
    combined_score: float = 0.0
    retrieval_metadata: dict = field(default_factory=dict)


def _tokenize(text: str) -> list[str]:
    words = re.findall(r"[a-zA-Z0-9.']+", (text or "").lower())
    return [
        word
        for word in words
        if len(word) >= 4 and word not in STOPWORDS
    ]


def extract_keywords_from_text(text: str, limit: int = 20) -> list[str]:
    from collections import Counter

    counts = Counter(_tokenize(text))
    return [word for word, _ in counts.most_common(limit)]


def _normalize_string_list(value) -> list[str]:
    if not isinstance(value, list):
        return []

    normalized = []
    seen = set()

    for item in value:
        cleaned = str(item or "").strip()
        lowered = cleaned.lower()

        if cleaned and lowered not in seen:
            normalized.append(cleaned)
            seen.add(lowered)

    return normalized


def collect_decomposed_issues(analysis: dict | None) -> list[dict]:
    if not analysis:
        return []

    issues = []

    for field_name, issue_type in ISSUE_TYPE_FIELDS:
        for index, item in enumerate(analysis.get(field_name) or []):
            if not isinstance(item, dict):
                continue

            issue_name = str(item.get("issue") or "").strip()
            if not issue_name:
                continue

            issue_id = str(item.get("issue_id") or "").strip()
            if not issue_id:
                issue_id = f"{issue_type}_{index + 1}"

            issues.append(
                {
                    "issue_id": issue_id,
                    "issue_type": issue_type,
                    "issue": issue_name,
                    "search_queries": _normalize_string_list(
                        item.get("search_queries", [])
                    ),
                    "legal_synonyms": _normalize_string_list(
                        item.get("legal_synonyms", [])
                    ),
                }
            )

    if not issues:
        primary = str(analysis.get("primary_issue") or "").strip()
        if primary:
            issues.append(
                {
                    "issue_id": "primary_1",
                    "issue_type": "primary",
                    "issue": primary,
                    "search_queries": [],
                    "legal_synonyms": [],
                }
            )

    return issues


def build_dispute_frame_summary(dispute_frame: dict | None) -> str:
    if not dispute_frame or not isinstance(dispute_frame, dict):
        return ""

    lines = []

    summary = str(dispute_frame.get("summary") or "").strip()
    if summary:
        lines.append(f"Dispute summary: {summary}")

    for field_name, label in (
        ("management_actions", "Management actions described"),
        ("employee_actions", "Employee actions described"),
        ("union_concerns", "Union concerns to verify"),
        ("information_sought", "Information or records sought"),
    ):
        items = _normalize_string_list(dispute_frame.get(field_name, []))
        if items:
            lines.append(f"{label}: {'; '.join(items)}")

    return "\n".join(lines)



SAFETY_ISSUE_TOKENS = {
    "unsafe",
    "safety",
    "inspection",
    "hazard",
    "hazardous",
    "equipment",
    "operation",
    "operating",
    "protective",
    "injury",
    "accident",
    "osha",
}


def _append_safety_queries_from_issue_tokens(queries: list[str], issue_text: str) -> None:
    lowered = issue_text.lower()
    if not any(token in lowered for token in SAFETY_ISSUE_TOKENS):
        return

    tokens = [
        word
        for word in _tokenize(issue_text)
        if len(word) >= 4 and word not in STOPWORDS
    ]
    if not tokens:
        return

    content_tokens = [
        word
        for word in tokens
        if word not in SAFETY_ISSUE_TOKENS
    ]
    focus = " ".join(content_tokens[:6] or tokens[:6])

    for word in (content_tokens[:8] or tokens[:8]):
        queries.append(f"{word} safety workplace obligation")
        queries.append(f"unsafe working conditions {word}")

    queries.append(f"workplace safety {focus}")
    queries.append(f"employee safety rights {focus}")
    queries.append(f"contract safety and health {focus}")
    queries.append(f"union safety inspection {focus}")




def build_issue_type_backfill_queries(
    issue: dict,
    dispute_frame: dict | None = None,
) -> list[str]:
    """Broader issue-type templates for empty per-issue pools after primary retrieval."""
    issue_type = str(issue.get("issue_type") or "").lower()
    templates = ISSUE_TYPE_BACKFILL_TEMPLATES.get(issue_type, [])
    if not templates:
        return []

    issue_name = str(issue.get("issue") or "").strip()
    queries: list[str] = []

    for template in templates:
        queries.append(template)
        if issue_name:
            queries.append(f"{issue_name} {template}")

    frame_summary = build_dispute_frame_summary(dispute_frame)
    if frame_summary and issue_name:
        queries.append(f"{issue_name} {frame_summary[:80]}")

    unique_queries: list[str] = []
    seen: set[str] = set()
    for query in queries:
        cleaned = str(query or "").strip()
        lowered = cleaned.lower()
        if cleaned and lowered not in seen:
            unique_queries.append(cleaned)
            seen.add(lowered)

    return unique_queries

def build_queries_for_issue(issue: dict, dispute_frame: dict | None) -> list[str]:
    queries = []

    issue_name = str(issue.get("issue") or "").strip()
    if issue_name:
        queries.append(issue_name)

    for query in issue.get("search_queries", []) or []:
        cleaned = str(query or "").strip()
        if cleaned:
            queries.append(cleaned)

    for synonym in issue.get("legal_synonyms", []) or []:
        cleaned = str(synonym or "").strip()
        if cleaned:
            queries.append(cleaned)

    frame_summary = build_dispute_frame_summary(dispute_frame)
    if frame_summary and issue_name:
        queries.append(f"{issue_name} {frame_summary[:120]}")

    issue_text = " ".join(queries)
    _append_safety_queries_from_issue_tokens(queries, issue_text)

    unique_queries = []
    seen = set()

    for query in queries:
        cleaned = str(query or "").strip()
        lowered = cleaned.lower()

        if cleaned and lowered not in seen:
            unique_queries.append(cleaned)
            seen.add(lowered)

    return unique_queries


def extract_issue_keywords_for_issue(
    issue: dict,
    dispute_frame: dict | None = None,
) -> list[str]:
    texts = []

    issue_name = str(issue.get("issue") or "").strip()
    if issue_name:
        texts.append(issue_name)

    for query in issue.get("search_queries", []) or []:
        cleaned = str(query or "").strip()
        if cleaned:
            texts.append(cleaned)

    for synonym in issue.get("legal_synonyms", []) or []:
        cleaned = str(synonym or "").strip()
        if cleaned:
            texts.append(cleaned)

    if dispute_frame:
        for field_name in (
            "summary",
            "management_actions",
            "employee_actions",
            "union_concerns",
            "information_sought",
        ):
            value = dispute_frame.get(field_name)
            if isinstance(value, list):
                texts.extend(str(item).strip() for item in value if str(item).strip())
            else:
                cleaned = str(value or "").strip()
                if cleaned:
                    texts.append(cleaned)

    seen = set()
    keywords = []

    for text in texts:
        for word in _tokenize(text):
            if word not in seen:
                seen.add(word)
                keywords.append(word)

    return keywords[:30]


def extract_issue_keywords(
    question: str,
    analysis: dict | None = None,
    expanded_queries: list[str] | None = None,
) -> list[str]:
    texts = [str(question or "").strip()]

    if analysis:
        primary = str(analysis.get("primary_issue") or "").strip()
        if primary:
            texts.append(primary)

        for category in analysis.get("issue_categories", []):
            cleaned = str(category or "").strip()
            if cleaned:
                texts.append(cleaned)

        for field_name, _issue_type in ISSUE_TYPE_FIELDS:
            for issue in analysis.get(field_name, []):
                if not isinstance(issue, dict):
                    continue

                issue_name = str(issue.get("issue") or "").strip()
                if issue_name:
                    texts.append(issue_name)

                for query in issue.get("search_queries", []):
                    cleaned = str(query or "").strip()
                    if cleaned:
                        texts.append(cleaned)

                for synonym in issue.get("legal_synonyms", []):
                    cleaned = str(synonym or "").strip()
                    if cleaned:
                        texts.append(cleaned)

        dispute_summary = build_dispute_frame_summary(
            analysis.get("dispute_frame")
        )
        if dispute_summary:
            texts.append(dispute_summary)

    if expanded_queries:
        texts.extend(str(q).strip() for q in expanded_queries if str(q).strip())

    seen = set()
    keywords = []

    for text in texts:
        for word in _tokenize(text):
            if word not in seen:
                seen.add(word)
                keywords.append(word)

    return keywords[:30]


def compute_substantive_score(text: str) -> float:
    lowered = (text or "").lower()
    if not lowered.strip():
        return 0.0

    hits = 0
    for signal in SUBSTANTIVE_SIGNALS:
        if signal in lowered:
            hits += 1

    return min(hits / 4.0, 1.0)


def is_procedural_only_passage(text: str) -> bool:
    lowered = (text or "").lower()
    if not lowered.strip():
        return False

    procedural_hits = sum(
        1 for signal in PROCEDURAL_ONLY_SIGNALS if signal in lowered
    )
    substantive_score = compute_substantive_score(text)

    return procedural_hits >= 2 and substantive_score < 0.25


def _extract_direction_signals(actions: list[str]) -> set[str]:
    signals: set[str] = set()

    for action in actions:
        raw_tokens = re.findall(r"[a-zA-Z0-9']+", (action or "").lower())
        for index in range(len(raw_tokens) - 1):
            left = raw_tokens[index]
            right = raw_tokens[index + 1]
            if left not in DIRECTION_GENERIC_TOKENS and right not in DIRECTION_GENERIC_TOKENS:
                signals.add(f"{left} {right}")

        for token in raw_tokens:
            if (
                len(token) >= 5
                and token not in DIRECTION_GENERIC_TOKENS
                and token not in STOPWORDS
            ):
                signals.add(token)

    return signals


def _frame_action_terms(dispute_frame: dict | None) -> tuple[set[str], set[str]]:
    management_terms = set(MANAGEMENT_ACTION_TERMS)
    employee_terms = set(EMPLOYEE_ACTION_TERMS)

    if not dispute_frame or not isinstance(dispute_frame, dict):
        return management_terms, employee_terms

    management_terms.update(
        _extract_direction_signals(
            _normalize_string_list(dispute_frame.get("management_actions", []))
        )
    )
    employee_terms.update(
        _extract_direction_signals(
            _normalize_string_list(dispute_frame.get("employee_actions", []))
        )
    )

    return management_terms, employee_terms


def _count_direction_signal_hits(lowered: str, terms: set[str]) -> int:
    hits = 0
    for term in terms:
        if " " in term:
            if term in lowered:
                hits += 1
        elif len(term) >= 5 and term in lowered:
            hits += 1
    return hits


def _opposite_direction_verbs(management_terms: set[str], employee_terms: set[str]) -> bool:
    management_verbs = {
        term
        for term in management_terms
        if " " not in term and term in MANAGEMENT_ACTION_TERMS
    }
    employee_verbs = {
        term
        for term in employee_terms
        if " " not in term and term in EMPLOYEE_ACTION_TERMS
    }
    if not management_verbs or not employee_verbs:
        return False
    return not management_verbs.isdisjoint(EMPLOYEE_ACTION_TERMS) or not employee_verbs.isdisjoint(
        MANAGEMENT_ACTION_TERMS
    )


def compute_direction_match_score(text: str, dispute_frame: dict | None) -> float:
    lowered = (text or "").lower()
    if not lowered.strip():
        return 0.0

    management_terms, employee_terms = _frame_action_terms(dispute_frame)

    management_hits = _count_direction_signal_hits(lowered, management_terms)
    employee_hits = _count_direction_signal_hits(lowered, employee_terms)
    total_hits = management_hits + employee_hits

    if total_hits == 0:
        return 0.0

    return max(management_hits, employee_hits) / total_hits


def compute_direction_penalty(text: str, dispute_frame: dict | None) -> float:
    if not dispute_frame or not isinstance(dispute_frame, dict):
        return 0.0

    lowered = (text or "").lower()
    if not lowered.strip():
        return 0.0

    management_terms, employee_terms = _frame_action_terms(dispute_frame)

    management_hits = _count_direction_signal_hits(lowered, management_terms)
    employee_hits = _count_direction_signal_hits(lowered, employee_terms)

    if management_hits == 0 and employee_hits == 0:
        return 0.0

    frame_management = _normalize_string_list(
        dispute_frame.get("management_actions", [])
    )
    frame_employee = _normalize_string_list(
        dispute_frame.get("employee_actions", [])
    )

    if management_hits > 0 and employee_hits > 0:
        if _opposite_direction_verbs(management_terms, employee_terms):
            return DIRECTION_CONTRADICTION_PENALTY * 0.5
        return 0.0

    if frame_management and employee_hits > management_hits:
        return DIRECTION_CONTRADICTION_PENALTY

    if frame_employee and management_hits > employee_hits:
        return DIRECTION_CONTRADICTION_PENALTY

    return 0.0


def passes_retrieval_gate(retrieved: RetrievedChunk, combined_score: float) -> bool:
    text = retrieved.chunk.text or ""
    emb = max(0.0, 1.0 - retrieved.best_embedding_distance)
    if combined_score >= MIN_COMBINED_RETRIEVAL_SCORE:
        return True
    if (
        emb >= EMBEDDING_FALLBACK_THRESHOLD
        and retrieved.matched_query_count >= 1
        and not is_boilerplate_chunk(text)
    ):
        return True
    if (
        emb >= MIN_EMBEDDING_SIMILARITY
        and compute_substantive_score(text) >= 0.25
        and not is_boilerplate_chunk(text)
    ):
        return True
    return False


def compute_keyword_overlap_score(text: str, issue_keywords: list[str]) -> float:
    if not issue_keywords:
        return 0.0

    text_lower = (text or "").lower()
    matches = sum(1 for keyword in issue_keywords if keyword in text_lower)
    return matches / len(issue_keywords)


def compute_distinctive_overlap_score(text: str, issue_keywords: list[str]) -> float:
    distinctive = [
        keyword
        for keyword in issue_keywords
        if keyword not in GENERIC_TOPIC_TERMS
    ]

    if not distinctive:
        return compute_keyword_overlap_score(text, issue_keywords)

    text_lower = (text or "").lower()
    matches = sum(1 for keyword in distinctive if keyword in text_lower)
    return matches / len(distinctive)


def is_boilerplate_chunk(text: str) -> bool:
    lowered = (text or "").lower()

    for pattern in BOILERPLATE_PATTERNS:
        if pattern in lowered:
            return True

    if lowered.count("article ") >= 8 and len(lowered) < 2500:
        return True

    return False




def extract_grounded_quote_snippet(
    chunk_text: str,
    issue_keywords: list[str] | None = None,
    max_length: int = 220,
) -> str:
    """Select a grounded quote snippet from chunk text for coverage promotion."""
    text = (chunk_text or "").strip()
    if not text:
        return ""

    sentences = re.split(r"(?<=[.!?])\s+", text)
    keywords = {w.lower() for w in (issue_keywords or []) if len(w) >= 4}
    best = ""
    best_score = -1.0

    for sentence in sentences:
        cleaned = sentence.strip()
        if len(cleaned) < 40:
            continue
        lowered = cleaned.lower()
        score = compute_substantive_score(cleaned)
        if keywords:
            overlap = sum(1 for kw in keywords if kw in lowered)
            score += overlap * 0.15
        if score > best_score:
            best_score = score
            best = cleaned

    if not best:
        best = text[:max_length].strip()

    if len(best) > max_length:
        best = best[:max_length].rstrip() + "..."

    return best if verify_quote_in_chunk(best, text) else text[:max_length].strip()

def normalize_quote(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").strip().lower())


def verify_quote_in_chunk(quote: str, chunk_text: str) -> bool:
    normalized_quote = normalize_quote(quote)
    normalized_chunk = normalize_quote(chunk_text)

    if not normalized_quote or not normalized_chunk:
        return False

    if normalized_quote in normalized_chunk:
        return True

    if len(normalized_quote) > 40:
        prefix = normalized_quote[:40]
        return prefix in normalized_chunk

    return False


def compute_procedural_bonus(text: str, issue_keywords: list[str]) -> float:
    lowered = (text or "").lower()
    bonus = 0.0

    for term in PROCEDURAL_SIGNAL_TERMS:
        if term in lowered:
            bonus += 0.02

    for keyword in issue_keywords:
        if keyword in lowered:
            bonus += 0.05

    if "shall" in lowered:
        bonus += 0.03
    if "must" in lowered:
        bonus += 0.02
    if "grievance" in lowered and "arbitration" in lowered:
        bonus += 0.03

    return min(bonus, 0.35)


def combine_retrieval_score(
    embedding_similarity: float,
    keyword_overlap: float,
    source_type: str,
    is_boilerplate: bool = False,
    procedural_bonus: float = 0.0,
) -> float:
    source_weight = SOURCE_TYPE_WEIGHTS.get(
        (source_type or "").upper(),
        DEFAULT_SOURCE_WEIGHT,
    )
    normalized_source = min(source_weight / 18.0, 1.0)

    keyword_component = min(keyword_overlap + procedural_bonus, 1.0)

    score = (
        EMBEDDING_SCORE_WEIGHT * max(embedding_similarity, 0.0)
        + KEYWORD_SCORE_WEIGHT * keyword_component
        + 0.05 * normalized_source
    )

    if is_boilerplate:
        score -= BOILERPLATE_PENALTY / 100.0

    return max(score, 0.0)


def _score_chunk_core(
    text: str,
    retrieved: RetrievedChunk,
    keywords: list[str],
    dispute_frame: dict | None,
    article_mentions: list[str] | None,
) -> tuple[float, float, bool]:
    source_type = (retrieved.chunk.source_document.source_type or "").upper()
    embedding_similarity = max(0.0, 1.0 - retrieved.best_embedding_distance)
    keyword_overlap = compute_distinctive_overlap_score(text, keywords)
    generic_overlap = compute_keyword_overlap_score(text, keywords)
    keyword_overlap = max(keyword_overlap, generic_overlap * 0.5)
    boilerplate = is_boilerplate_chunk(text)
    procedural_bonus = compute_procedural_bonus(text, keywords)

    for mention in article_mentions or []:
        if mention in text.lower():
            keyword_overlap = min(keyword_overlap + 0.08, 1.0)

    score = combine_retrieval_score(
        embedding_similarity=embedding_similarity,
        keyword_overlap=keyword_overlap,
        source_type=source_type,
        is_boilerplate=boilerplate,
        procedural_bonus=procedural_bonus,
    )

    if compute_substantive_score(text) >= 0.25:
        score += SUBSTANTIVE_RULE_BONUS

    if is_procedural_only_passage(text):
        score -= PROCEDURAL_ONLY_PENALTY

    score -= compute_direction_penalty(text, dispute_frame)
    score = max(score, 0.0)

    return score, keyword_overlap, boilerplate


def score_chunk_for_issue(
    retrieved: RetrievedChunk,
    issue_keywords: list[str],
    dispute_frame: dict | None = None,
    issue: dict | None = None,
    article_mentions: list[str] | None = None,
    global_keywords: list[str] | None = None,
) -> float:
    chunk = retrieved.chunk
    text = chunk.text or ""

    issue_score, keyword_overlap, boilerplate = _score_chunk_core(
        text,
        retrieved,
        issue_keywords,
        dispute_frame,
        article_mentions,
    )
    score = issue_score

    if global_keywords:
        global_score, global_overlap, _ = _score_chunk_core(
            text,
            retrieved,
            global_keywords,
            dispute_frame,
            article_mentions,
        )
        score = max(issue_score, global_score)
        keyword_overlap = max(keyword_overlap, global_overlap)

    embedding_similarity = max(0.0, 1.0 - retrieved.best_embedding_distance)

    matched_issue_ids = list(
        retrieved.retrieval_metadata.get("matched_issue_ids", [])
    )
    if issue and issue.get("issue_id"):
        issue_id = str(issue["issue_id"])
        if issue_id not in matched_issue_ids:
            matched_issue_ids.append(issue_id)

    retrieved.keyword_overlap = keyword_overlap
    retrieved.combined_score = score
    retrieved.retrieval_metadata = {
        **(retrieved.retrieval_metadata or {}),
        "embedding_similarity": round(embedding_similarity, 4),
        "keyword_overlap": round(keyword_overlap, 4),
        "matched_query_count": retrieved.matched_query_count,
        "is_boilerplate": boilerplate,
        "substantive_score": round(compute_substantive_score(text), 4),
        "direction_penalty": round(compute_direction_penalty(text, dispute_frame), 4),
        "matched_issue_ids": matched_issue_ids,
    }

    if issue:
        retrieved.retrieval_metadata["primary_issue_id"] = issue.get("issue_id")

    return score


def merge_issue_retrieval_pools(
    issue_pools: dict[str, list],
    max_total: int,
) -> tuple[list, dict]:
    merged_by_key: dict[tuple, RetrievedChunk] = {}
    per_issue_counts: dict[str, int] = {}

    for issue_id, pool in (issue_pools or {}).items():
        sorted_pool = sorted(
            pool or [],
            key=lambda item: getattr(item, "combined_score", 0.0),
            reverse=True,
        )
        kept = 0

        for retrieved in sorted_pool[:MAX_CHUNKS_PER_ISSUE]:
            chunk = retrieved.chunk
            key = (
                chunk.source_document_id,
                chunk.page_number,
                chunk.chunk_index,
            )

            if key not in merged_by_key:
                merged_by_key[key] = retrieved
            else:
                existing = merged_by_key[key]
                existing_ids = set(
                    existing.retrieval_metadata.get("matched_issue_ids", [])
                )
                new_ids = set(
                    retrieved.retrieval_metadata.get("matched_issue_ids", [])
                )
                existing_ids.update(new_ids)
                existing.retrieval_metadata["matched_issue_ids"] = sorted(
                    existing_ids
                )
                if retrieved.combined_score > existing.combined_score:
                    existing.combined_score = retrieved.combined_score
                    existing.keyword_overlap = retrieved.keyword_overlap
                    existing.best_embedding_distance = (
                        retrieved.best_embedding_distance
                    )
                    existing.matched_query_count = max(
                        existing.matched_query_count,
                        retrieved.matched_query_count,
                    )

            kept += 1

        per_issue_counts[issue_id] = kept

    merged = sorted(
        merged_by_key.values(),
        key=lambda item: item.combined_score,
        reverse=True,
    )

    if len(merged) > max_total:
        merged = merged[:max_total]

    for issue_id, pool in (issue_pools or {}).items():
        if len(pool or []) < MIN_CHUNKS_PER_ISSUE:
            per_issue_counts.setdefault(issue_id, len(pool or []))

    metadata = {
        "per_issue_counts": per_issue_counts,
        "total_merged": len(merged),
    }

    return merged, metadata


def build_issue_context_summary(analysis: dict | None) -> str:
    if not analysis:
        return ""

    lines = []

    dispute_summary = build_dispute_frame_summary(
        analysis.get("dispute_frame")
    )
    if dispute_summary:
        lines.append(dispute_summary)

    primary = str(analysis.get("primary_issue") or "").strip()
    if primary:
        lines.append(f"Primary issue: {primary}")

    categories = analysis.get("issue_categories") or []
    if categories:
        lines.append(f"Issue categories: {', '.join(categories)}")

    label_map = {
        "legal_issues": "Legal issues to research",
        "remedial_issues": "Remedy issues to research",
        "timeline_issues": "Timeline issues to research",
        "information_rights_issues": "Information rights issues to research",
        "local_agreement_issues": "Local agreement issues to research",
    }

    for field_name, label in label_map.items():
        issues = analysis.get(field_name) or []
        for issue in issues:
            if not isinstance(issue, dict):
                continue
            name = str(issue.get("issue") or "").strip()
            if name:
                lines.append(f"{label}: {name}")

    facts = analysis.get("facts_needed") or []
    if facts:
        lines.append(f"Facts still needed: {'; '.join(facts)}")

    return "\n".join(lines)
