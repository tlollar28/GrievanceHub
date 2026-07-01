class QueryExpansionService:
    @staticmethod
    def expand(question: str) -> list[str]:
        base_queries = [
            question,
            f"{question} grievance rights",
            f"{question} contract violation",
            f"{question} employee rights",
            f"{question} union rights",
            f"{question} management obligations",
            f"{question} remedy",
            f"{question} information request",
            f"{question} just cause",
            f"{question} grievance arbitration procedure",
        ]

        cleaned = []

        for query in base_queries:
            query = query.strip()
            if query and query not in cleaned:
                cleaned.append(query)

        return cleaned
        ...