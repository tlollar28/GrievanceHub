from app.services.relevance_utils import verify_quote_in_chunk


class CitationValidator:
    AUTHORITY_SECTION_KEYS = (
        "key_contract_violations",
        "union_supporting_authority",
        "management_limiting_authority",
        "procedural_requirements",
        "information_rights",
        "timeline_requirements",
        "remedy_authority",
        "background_authority",
    )

    @staticmethod
    def _find_authority_chunk(
        ranked_authorities: list[dict],
        document_name: str,
        page,
        chunk,
    ):
        for authority in ranked_authorities:
            if (
                authority.get("document_name") == document_name
                and authority.get("page") == page
                and authority.get("chunk_index") == chunk
            ):
                return authority.get("chunk")

        return None

    @staticmethod
    def validate_report(
        report: dict,
        evidence_items: list[dict],
        ranked_authorities: list[dict] | None = None,
    ) -> dict:
        ranked_authorities = ranked_authorities or []

        evidence_quotes = {
            item.get("direct_quote", "").strip()
            for item in evidence_items
            if item.get("direct_quote")
        }

        validation_notes = []

        if not evidence_items:
            validation_notes.append(
                "No supporting evidence items were extracted."
            )

        for item in evidence_items:
            quote = item.get("direct_quote", "")

            if not quote:
                validation_notes.append(
                    "An evidence item is missing a direct quote."
                )

            if not item.get("document_name"):
                validation_notes.append(
                    "An evidence item is missing a document name."
                )

            if item.get("page") is None:
                validation_notes.append(
                    "An evidence item is missing a page number."
                )

            chunk = CitationValidator._find_authority_chunk(
                ranked_authorities,
                item.get("document_name"),
                item.get("page"),
                item.get("chunk"),
            )

            if chunk and not verify_quote_in_chunk(quote, chunk.text or ""):
                validation_notes.append(
                    "An evidence item contains a quote not grounded in the source excerpt."
                )

        for section_key in CitationValidator.AUTHORITY_SECTION_KEYS:
            for item in report.get(section_key, []):
                quote = item.get("direct_quote", "")
                citation = item.get("citation", {})

                chunk = CitationValidator._find_authority_chunk(
                    ranked_authorities,
                    citation.get("document_name"),
                    citation.get("page"),
                    citation.get("chunk"),
                )

                if chunk and quote and not verify_quote_in_chunk(
                    quote,
                    chunk.text or "",
                ):
                    validation_notes.append(
                        f"A quote in {section_key} is not grounded in the source excerpt."
                    )

        report["citation_validation"] = {
            "status": "Passed" if not validation_notes else "Needs Review",
            "evidence_items_checked": len(evidence_items),
            "direct_quotes_found": len(evidence_quotes),
            "notes": validation_notes,
        }

        return report
