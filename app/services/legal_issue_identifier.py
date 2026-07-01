import json
import os

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()


class LegalIssueIdentifier:
    @staticmethod
    def _client():
        return OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

    @staticmethod
    def _safe_json_loads(content: str, fallback: dict):
        try:
            return json.loads(content)
        except Exception:
            return fallback

    @staticmethod
    def identify_issues(
        question: str,
        ranked_authorities: list[dict],
        issue_analysis: dict | None = None,
        known_facts: list[str] | None = None,
    ) -> dict:
        client = LegalIssueIdentifier._client()
        issue_analysis = issue_analysis or {}
        known_facts = known_facts or []

        dispute_frame = str(issue_analysis.get("dispute_frame") or "").strip()
        if not dispute_frame:
            dispute_frame = str(issue_analysis.get("primary_issue") or question).strip()

        authority_summaries = [
            {
                "document_name": item["document_name"],
                "document_type": item["document_type"],
                "page": item["page"],
                "chunk": item["chunk_index"],
                "article_or_section": item["article_or_section"],
                "direct_quote": item["direct_quote"],
                "why_it_matters": item["why_it_matters"],
                "legal_issue": item["legal_issue"],
                "relevance_score": item["relevance_score"],
            }
            for item in ranked_authorities
        ]

        research_context = {
            "dispute_frame": dispute_frame,
            "primary_issue": issue_analysis.get("primary_issue"),
            "issue_categories": issue_analysis.get("issue_categories", []),
            "facts_needed": issue_analysis.get("facts_needed", []),
            "known_facts": known_facts,
        }

        response = client.chat.completions.create(
            model="gpt-4o-mini",
            response_format={"type": "json_object"},
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You identify USPS/NPMHU grievance issues from ranked authorities. "
                        "Use only the provided authorities and dispute frame. "
                        "Do not invent facts or articles. Return valid JSON only."
                    ),
                },
                {
                    "role": "user",
                    "content": f"""
User question:
{question}

Dispute frame (neutral case framing — do not expand beyond stated/known facts):
{dispute_frame}

Research context:
{json.dumps(research_context, indent=2)}

Ranked authorities:
{json.dumps(authority_summaries, indent=2)}

Return JSON exactly like this:

{{
  "primary_issue": "Main grievance/legal issue",
  "secondary_issues": [
    "Additional issue"
  ],
  "likely_violations": [
    {{
      "article_or_section": "Article/section from authority only",
      "issue": "What this provision supports",
      "why_relevant": "Why it matters"
    }}
  ],
  "missing_facts": [
    "Fact needed to strengthen or confirm the grievance"
  ],
  "grievability": "Likely Grievable / Possibly Grievable / Not Enough Information",
  "confidence": "High / Medium / Low"
}}

Rules:
- Keep secondary_issues distinct from primary_issue.
- Do not list an article or section unless it appears in a ranked authority.
- Treat known_facts as supplied by the steward; do not invent additional facts.
""",
                },
            ],
        )

        parsed = LegalIssueIdentifier._safe_json_loads(
            response.choices[0].message.content,
            {
                "primary_issue": "Unable to identify issue",
                "secondary_issues": [],
                "likely_violations": [],
                "missing_facts": [],
                "grievability": "Not Enough Information",
                "confidence": "Low",
            },
        )

        if not isinstance(parsed.get("secondary_issues"), list):
            parsed["secondary_issues"] = []

        return parsed
