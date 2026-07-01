import copy
import json
import os

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()


class LegalIssueAnalyzer:
    """
    Breaks a steward's question into neutral research issues before retrieval.

    This service does not decide the grievance, invent contract provisions,
    or recommend a final remedy. It only creates broad, concept-based search
    queries for the sources GrievanceHub currently supports.
    """

    ALLOWED_SOURCE_TYPES = {
        "CONTRACT",
        "ELM",
        "CIM",
        "LMOU",
    }

    ISSUE_LIST_FIELDS = (
        "legal_issues",
        "remedial_issues",
        "timeline_issues",
        "information_rights_issues",
        "local_agreement_issues",
    )

    _cache: dict[str, dict] = {}

    @staticmethod
    def _client():
        return OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

    @staticmethod
    def invalidate_cache():
        LegalIssueAnalyzer._cache.clear()

    @staticmethod
    def _safe_json_loads(content: str, fallback: dict) -> dict:
        try:
            parsed = json.loads(content)

            if isinstance(parsed, dict):
                return parsed

            return fallback
        except Exception:
            return fallback

    @staticmethod
    def _empty_analysis(question: str) -> dict:
        return {
            "primary_issue": question,
            "issue_categories": [],
            "legal_issues": [],
            "facts_needed": [],
            "possible_sources": [
                "CONTRACT",
                "ELM",
                "CIM",
                "LMOU",
            ],
            "remedial_issues": [],
            "timeline_issues": [],
            "information_rights_issues": [],
            "local_agreement_issues": [],
            "dispute_frame": {
                "summary": "",
                "management_actions": [],
                "employee_actions": [],
                "union_concerns": [],
                "information_sought": [],
            },
        }

    @staticmethod
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

    @staticmethod
    def _normalize_dispute_frame(value) -> dict:
        fallback = LegalIssueAnalyzer._empty_analysis("")["dispute_frame"]

        if not isinstance(value, dict):
            return copy.deepcopy(fallback)

        return {
            "summary": str(value.get("summary") or "").strip(),
            "management_actions": LegalIssueAnalyzer._normalize_string_list(
                value.get("management_actions", [])
            ),
            "employee_actions": LegalIssueAnalyzer._normalize_string_list(
                value.get("employee_actions", [])
            ),
            "union_concerns": LegalIssueAnalyzer._normalize_string_list(
                value.get("union_concerns", [])
            ),
            "information_sought": LegalIssueAnalyzer._normalize_string_list(
                value.get("information_sought", [])
            ),
        }

    @staticmethod
    def _normalize_issue_list(value, field_name: str = "issue") -> list[dict]:
        if not isinstance(value, list):
            return []

        normalized = []

        for index, item in enumerate(value):
            if not isinstance(item, dict):
                continue

            issue = str(item.get("issue") or "").strip()
            why_it_matters = str(
                item.get("why_it_matters") or ""
            ).strip()

            issue_id = str(item.get("issue_id") or "").strip()
            if not issue_id:
                issue_id = f"{field_name}_{index + 1}"

            raw_queries = item.get("search_queries", [])

            if not isinstance(raw_queries, list):
                raw_queries = []

            search_queries = []
            seen_queries = set()

            for query in raw_queries:
                cleaned = str(query or "").strip()
                lowered = cleaned.lower()

                if cleaned and lowered not in seen_queries:
                    search_queries.append(cleaned)
                    seen_queries.add(lowered)

            legal_synonyms = LegalIssueAnalyzer._normalize_string_list(
                item.get("legal_synonyms", [])
            )

            if issue:
                normalized.append(
                    {
                        "issue_id": issue_id,
                        "issue": issue,
                        "why_it_matters": why_it_matters,
                        "search_queries": search_queries,
                        "legal_synonyms": legal_synonyms,
                    }
                )

        return normalized

    @staticmethod
    def _normalize_sources(value) -> list[str]:
        if not isinstance(value, list):
            return [
                "CONTRACT",
                "ELM",
                "CIM",
                "LMOU",
            ]

        normalized = []

        for item in value:
            source_type = str(item or "").strip().upper()

            if (
                source_type in LegalIssueAnalyzer.ALLOWED_SOURCE_TYPES
                and source_type not in normalized
            ):
                normalized.append(source_type)

        if normalized:
            return normalized

        return [
            "CONTRACT",
            "ELM",
            "CIM",
            "LMOU",
        ]

    @staticmethod
    def _normalize_analysis(
        question: str,
        analysis: dict,
    ) -> dict:
        normalized = LegalIssueAnalyzer._empty_analysis(
            question
        )

        primary_issue = str(
            analysis.get("primary_issue") or question
        ).strip()

        normalized["primary_issue"] = (
            primary_issue if primary_issue else question
        )

        normalized["issue_categories"] = (
            LegalIssueAnalyzer._normalize_string_list(
                analysis.get("issue_categories", [])
            )
        )

        normalized["facts_needed"] = (
            LegalIssueAnalyzer._normalize_string_list(
                analysis.get("facts_needed", [])
            )
        )

        normalized["possible_sources"] = (
            LegalIssueAnalyzer._normalize_sources(
                analysis.get("possible_sources", [])
            )
        )

        normalized["dispute_frame"] = (
            LegalIssueAnalyzer._normalize_dispute_frame(
                analysis.get("dispute_frame", {})
            )
        )

        for field in LegalIssueAnalyzer.ISSUE_LIST_FIELDS:
            normalized[field] = (
                LegalIssueAnalyzer._normalize_issue_list(
                    analysis.get(field, []),
                    field_name=field,
                )
            )

        return normalized

    @staticmethod
    def _cache_key(question: str, known_facts: list[str] | None) -> str:
        facts = LegalIssueAnalyzer._normalize_string_list(known_facts or [])
        return json.dumps(
            {
                "question": question.lower(),
                "known_facts": facts,
            },
            sort_keys=True,
        )

    @staticmethod
    def analyze(
        question: str,
        known_facts: list[str] | None = None,
    ) -> dict:
        cleaned_question = str(question or "").strip()
        normalized_facts = LegalIssueAnalyzer._normalize_string_list(
            known_facts or []
        )

        if not cleaned_question:
            return LegalIssueAnalyzer._empty_analysis("")

        cache_key = LegalIssueAnalyzer._cache_key(
            cleaned_question,
            normalized_facts,
        )

        if cache_key in LegalIssueAnalyzer._cache:
            return copy.deepcopy(
                LegalIssueAnalyzer._cache[cache_key]
            )

        fallback = LegalIssueAnalyzer._empty_analysis(
            cleaned_question
        )

        known_facts_block = ""
        if normalized_facts:
            known_facts_block = (
                "\nKnown facts supplied by the steward (treat as stated, "
                "not verified contract language):\n"
                + "\n".join(f"- {fact}" for fact in normalized_facts)
            )

        response = LegalIssueAnalyzer._client().chat.completions.create(
            model="gpt-4o-mini",
            temperature=0,
            response_format={"type": "json_object"},
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a USPS/NPMHU grievance research issue analyzer. "
                        "Your only job is to identify the issues that should be researched "
                        "before an answer is written. Do not decide whether the grievance "
                        "will succeed. Do not decide who is correct. Do not state that a "
                        "contractual right, violation, obligation, deadline, or remedy "
                        "definitely exists before sources are retrieved. Do not invent facts, "
                        "article numbers, section numbers, manual provisions, cases, source "
                        "names, or remedies. Phrase why_it_matters neutrally as something "
                        "that should be verified. Search queries must be concept-based. "
                        "The only source labels allowed are CONTRACT, ELM, CIM, and LMOU. "
                        "Do not mention MRS, JCAM, Step 4 settlements, arbitration cases, "
                        "union bylaws, handbooks, or any other unavailable source. "
                        "Return valid JSON only."
                    ),
                },
                {
                    "role": "user",
                    "content": f"""
Question:
{cleaned_question}
{known_facts_block}

Return JSON exactly in this structure:

{{
  "primary_issue": "Neutral description of the main issue",
  "issue_categories": [
    "leave",
    "information_request"
  ],
  "dispute_frame": {{
    "summary": "Neutral one-sentence dispute frame",
    "management_actions": [
      "Neutral management action described in the question"
    ],
    "employee_actions": [
      "Neutral employee action described in the question"
    ],
    "union_concerns": [
      "Neutral union concern to verify"
    ],
    "information_sought": [
      "Records or information the steward may need"
    ]
  }},
  "legal_issues": [
    {{
      "issue_id": "legal_1",
      "issue": "Neutral issue to research",
      "why_it_matters": "What must be verified and why it could matter",
      "search_queries": [
        "concept-based search phrase",
        "related contractual concept"
      ],
      "legal_synonyms": [
        "alternate neutral phrase"
      ]
    }}
  ],
  "facts_needed": [
    "Specific missing fact needed for a reliable answer"
  ],
  "possible_sources": [
    "CONTRACT",
    "ELM",
    "CIM",
    "LMOU"
  ],
  "remedial_issues": [
    {{
      "issue_id": "remedy_1",
      "issue": "Possible remedy issue to research",
      "why_it_matters": "Why this possible remedy requires source support",
      "search_queries": [
        "make whole remedy",
        "reimbursement documented loss"
      ],
      "legal_synonyms": []
    }}
  ],
  "timeline_issues": [
    {{
      "issue_id": "timeline_1",
      "issue": "Possible deadline or timing issue",
      "why_it_matters": "Which deadline must be verified",
      "search_queries": [
        "grievance filing time limit",
        "response deadline grievance"
      ],
      "legal_synonyms": []
    }}
  ],
  "information_rights_issues": [
    {{
      "issue_id": "information_1",
      "issue": "Possible information or records issue",
      "why_it_matters": "Why access to records may matter",
      "search_queries": [
        "union information request",
        "personnel file access"
      ],
      "legal_synonyms": []
    }}
  ],
  "local_agreement_issues": [
    {{
      "issue_id": "local_1",
      "issue": "Possible LMOU or local practice issue",
      "why_it_matters": "Why local language may need review",
      "search_queries": [
        "LMOU annual leave procedure",
        "local leave selection procedure"
      ],
      "legal_synonyms": []
    }}
  ]
}}

Rules:
- Identify all reasonably related research issues.
- Include employee rights, union rights, management obligations,
  procedures, information rights, remedies, timelines, and LMOU issues
  only when reasonably connected to the question.
- Separate facts stated by the user from facts still needing confirmation.
- Do not say a rule applies until retrieved authority supports it.
- Do not say management violated anything.
- Do not say an employee is entitled to a remedy.
- Do not guess article or section numbers.
- Do not include unsupported accusations such as bad faith or unfair labor
  practices unless the user's stated facts specifically raise that issue.
- Keep each search query short and useful for semantic retrieval.
- Return JSON only.
""",
                },
            ],
        )

        parsed = LegalIssueAnalyzer._safe_json_loads(
            response.choices[0].message.content or "",
            fallback,
        )

        normalized = LegalIssueAnalyzer._normalize_analysis(
            cleaned_question,
            parsed,
        )

        LegalIssueAnalyzer._cache[cache_key] = copy.deepcopy(
            normalized
        )

        return normalized

    @staticmethod
    def build_search_queries(
        question: str,
        analysis: dict,
    ) -> list[str]:
        queries = [str(question or "").strip()]

        primary_issue = str(
            analysis.get("primary_issue") or ""
        ).strip()

        if primary_issue:
            queries.append(primary_issue)

        for category in analysis.get(
            "issue_categories",
            [],
        ):
            cleaned_category = str(category or "").strip()

            if cleaned_category:
                queries.append(cleaned_category)

        for field in LegalIssueAnalyzer.ISSUE_LIST_FIELDS:
            for issue in analysis.get(field, []):
                if not isinstance(issue, dict):
                    continue

                issue_name = str(
                    issue.get("issue") or ""
                ).strip()

                if issue_name:
                    queries.append(issue_name)

                for query in issue.get(
                    "search_queries",
                    [],
                ):
                    cleaned_query = str(query or "").strip()

                    if cleaned_query:
                        queries.append(cleaned_query)

                for synonym in issue.get(
                    "legal_synonyms",
                    [],
                ):
                    cleaned_synonym = str(synonym or "").strip()

                    if cleaned_synonym:
                        queries.append(cleaned_synonym)

        unique_queries = []
        seen = set()

        for query in queries:
            cleaned = str(query or "").strip()
            lowered = cleaned.lower()

            if cleaned and lowered not in seen:
                unique_queries.append(cleaned)
                seen.add(lowered)

        return unique_queries
