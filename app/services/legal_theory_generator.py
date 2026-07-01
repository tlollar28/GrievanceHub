import json
import os

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()


class LegalTheoryGenerator:
    @staticmethod
    def _client():
        return OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

    @staticmethod
    def generate(question: str) -> list[str]:
        client = LegalTheoryGenerator._client()

        response = client.chat.completions.create(
            model="gpt-4o-mini",
            response_format={"type": "json_object"},
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are an expert USPS/NPMHU labor relations specialist. "
                        "Your job is NOT to answer the grievance. "
                        "Your job is ONLY to identify every legal theory, contractual theory, "
                        "manual, procedural issue, and management obligation that should be researched "
                        "based on the user's question. "
                        "Think like a veteran union advocate. "
                        "Do not invent facts. "
                        "Return JSON only."
                    ),
                },
                {
                    "role": "user",
                    "content": f"""
Question:

{question}

Return JSON exactly like this:

{{
  "legal_theories":[
    {{
      "name":"Just Cause",
      "reason":"Why this legal theory may apply",
      "search_terms":[
        "just cause",
        "discipline",
        "Article 16"
      ]
    }}
  ]
}}

Rules:

- Generate EVERY legal theory that could reasonably apply.
- Include procedural theories.
- Include contractual theories.
- Include ELM/CIM theories if applicable.
- Include information request theories if applicable.
- Include management obligation theories.
- Include grievance procedure theories.
- Include steward rights if applicable.
- Include employee rights if applicable.
- Return ONLY JSON.
""",
                },
            ],
        )

        data = json.loads(response.choices[0].message.content)

        expanded_queries = [question]

        for theory in data.get("legal_theories", []):
            expanded_queries.extend(theory.get("search_terms", []))

        # Remove duplicates while preserving order
        seen = set()
        final_queries = []

        for query in expanded_queries:
            q = query.strip()

            if q and q not in seen:
                final_queries.append(q)
                seen.add(q)

        return final_queries