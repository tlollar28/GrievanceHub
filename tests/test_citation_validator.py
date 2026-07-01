from app.services.citation_validator import CitationValidator


def test_ungrounded_quotes_fail_validation(mock_chunk_factory):
    chunk = mock_chunk_factory(
        "Employees who have annual leave approved are entitled to such annual leave."
    )

    ranked_authorities = [
        {
            "document_name": "NPMHU CIM v6",
            "document_type": "CIM",
            "page": 137,
            "chunk_index": 242,
            "chunk": chunk,
        }
    ]

    report = {
        "key_contract_violations": [
            {
                "direct_quote": "This quote does not exist in the source.",
                "citation": {
                    "document_name": "NPMHU CIM v6",
                    "page": 137,
                    "chunk": 242,
                },
            }
        ],
        "union_supporting_authority": [],
        "management_limiting_authority": [],
    }

    evidence_items = [
        {
            "direct_quote": "Also not in the source at all.",
            "document_name": "NPMHU CIM v6",
            "page": 137,
            "chunk": 242,
        }
    ]

    validated = CitationValidator.validate_report(
        report=report,
        evidence_items=evidence_items,
        ranked_authorities=ranked_authorities,
    )

    assert validated["citation_validation"]["status"] == "Needs Review"
    assert len(validated["citation_validation"]["notes"]) >= 1


def test_grounded_quotes_pass_validation(mock_chunk_factory):
    chunk = mock_chunk_factory(
        "Employees who have annual leave approved are entitled to such annual leave."
    )

    ranked_authorities = [
        {
            "document_name": "NPMHU CIM v6",
            "document_type": "CIM",
            "page": 137,
            "chunk_index": 242,
            "chunk": chunk,
        }
    ]

    quote = "annual leave approved are entitled to such annual leave"

    report = {
        "key_contract_violations": [
            {
                "direct_quote": quote,
                "citation": {
                    "document_name": "NPMHU CIM v6",
                    "page": 137,
                    "chunk": 242,
                },
            }
        ],
        "union_supporting_authority": [],
        "management_limiting_authority": [],
    }

    evidence_items = [
        {
            "direct_quote": quote,
            "document_name": "NPMHU CIM v6",
            "page": 137,
            "chunk": 242,
        }
    ]

    validated = CitationValidator.validate_report(
        report=report,
        evidence_items=evidence_items,
        ranked_authorities=ranked_authorities,
    )

    assert validated["citation_validation"]["status"] == "Passed"
