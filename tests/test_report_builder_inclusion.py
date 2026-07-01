from app.services.report_builder import ReportBuilder


def test_low_score_union_supporting_excluded_from_key_violations():
    ranked_authorities = [
        {
            "role": "union_supporting",
            "relevance_score": 90,
            "legal_issue": "Strong authority",
            "article_or_section": "Article 10",
            "authority_type": "Union-Supporting",
            "direct_quote": "Employees who have annual leave approved are entitled.",
            "why_it_matters": "Directly supports grievance.",
            "document_name": "CIM",
            "document_type": "CIM",
            "page": 137,
            "chunk_index": 242,
        },
        {
            "role": "union_supporting",
            "relevance_score": 60,
            "legal_issue": "Weak tangential authority",
            "article_or_section": "Article 10",
            "authority_type": "Union-Supporting",
            "direct_quote": "An employee who is on extended absence may use annual leave.",
            "why_it_matters": "Topically similar but weak.",
            "document_name": "CIM",
            "document_type": "CIM",
            "page": 171,
            "chunk_index": 308,
        },
        {
            "role": "management_limiting",
            "relevance_score": 55,
            "legal_issue": "Management rights",
            "article_or_section": "Article 3",
            "authority_type": "Management-Limiting",
            "direct_quote": "Management retains the right to assign work.",
            "why_it_matters": "Must be distinguished.",
            "document_name": "Contract",
            "document_type": "CONTRACT",
            "page": 5,
            "chunk_index": 12,
        },
    ]

    report = ReportBuilder.build_report(
        question="Can management cancel approved leave?",
        legal_issues={
            "primary_issue": "Leave cancellation",
            "missing_facts": [],
            "grievability": "Possibly Grievable",
            "confidence": "Medium",
        },
        evidence_items=[],
        ranked_authorities=ranked_authorities,
    )

    key_quotes = {
        item["direct_quote"]
        for item in report["key_contract_violations"]
    }

    assert any("annual leave approved" in quote for quote in key_quotes)
    assert not any("extended absence" in quote for quote in key_quotes)
    assert len(report["management_limiting_authority"]) == 1


def test_report_uses_grievancehub_branding():
    report = ReportBuilder.build_report(
        question="Test question",
        legal_issues={"primary_issue": "Test", "missing_facts": []},
        evidence_items=[],
        ranked_authorities=[],
    )

    assert report["report_title"] == "GrievanceHub Analysis Report"
    assert report["brand"] == "GrievanceHub"
    assert "CREA" not in report["report_title"]
