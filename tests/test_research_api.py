"""Browser-safe Sources Research boundary (W6 M9)."""

from __future__ import annotations

import json
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.schemas.research_schema import (
    ResearchPassageDetail,
    ResearchSearchRequest,
    ResearchSearchResultItem,
    ResearchSourceDetail,
    ResearchSourceListResponse,
)
from app.services.research_service import (
    AUTHORITY_NOTICE,
    ResearchNotFoundError,
    ResearchService,
    SOURCE_TYPE_LABELS,
    map_retrieval_ui_status,
)
from app.services.retrieval.models import (
    AgentFailure,
    OrchestrationResult,
    RetrievalAuthorizationContext,
    RetrievalEvidence,
)


READ_KEY = "test-read-key-not-for-production"
ADMIN_KEY = "test-admin-key-not-for-production"


def _evidence(**overrides) -> RetrievalEvidence:
    values = dict(
        source_document_id=11,
        canonical_source_id="contract-na",
        source_title="National Agreement",
        source_type="CONTRACT",
        source_version="2022",
        source_sha256="abc123",
        chunk_id=101,
        chunk_index=3,
        page_number=12,
        chunk_text="Article 16 governs overtime assignments for regulars.",
        raw_vector_distance=0.2,
        raw_vector_similarity=0.8,
        normalized_score=0.77,
        final_relevance_score=0.81,
        retrieval_agent="ContractAgent",
        retrieval_domain="contract",
        evidence_role="contract_controlling",
        processing_strategy="pdf_text",
        safe_chunk_metadata={
            "article": "16",
            "section": "Overtime",
            "heading": "Overtime",
            "page": 12,
            "local_path": "/secret/path.pdf",
            "embedding": [0.1, 0.2],
        },
        content_trust="indexed_authority",
    )
    values.update(overrides)
    return RetrievalEvidence(**values)


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def auth_env(monkeypatch):
    monkeypatch.setenv("GRIEVANCEHUB_API_KEY", READ_KEY)
    monkeypatch.setenv("GRIEVANCEHUB_ADMIN_API_KEY", ADMIN_KEY)


def test_meta_requires_no_api_key(client):
    response = client.get("/research/meta")
    assert response.status_code == 200
    payload = response.json()
    assert payload["authority_notice"] == AUTHORITY_NOTICE
    assert "CONTRACT" in {item["value"] for item in payload["source_types"]}
    assert payload["max_limit"] == 24
    assert "browser-safe" in payload["boundary"].lower()
    dumped = json.dumps(payload)
    assert "embedding" not in dumped
    assert "local_path" not in dumped
    assert READ_KEY not in dumped
    assert "postgresql" not in dumped.lower()


def test_search_succeeds_without_api_key(client):
    result = OrchestrationResult(
        status="success",
        results=(_evidence(),),
        partial=False,
    )
    with patch(
        "app.services.research_service.KnowledgeRetrievalService.retrieve_with_agents",
        return_value=result,
    ) as mock_retrieve:
        response = client.post(
            "/research/search",
            json={"query": "overtime article 16", "limit": 5},
        )
    assert response.status_code == 200
    payload = response.json()
    assert payload["retrieval_status"] == "ok"
    assert payload["result_count"] == 1
    item = payload["results"][0]
    assert item["source_title"] == "National Agreement"
    assert item["source_type_label"] == SOURCE_TYPE_LABELS["CONTRACT"]
    assert item["passage_text"].startswith("Article 16")
    assert item["final_relevance_score"] == 0.81
    assert "local_path" not in item
    assert "embedding" not in item
    assert "source_sha256" not in item
    assert "raw_vector_distance" not in item
    dumped = json.dumps(payload)
    assert "/secret/path" not in dumped
    assert "GRIEVANCEHUB_API_KEY" not in dumped
    authorization = mock_retrieve.call_args.args[2]
    assert isinstance(authorization, RetrievalAuthorizationContext)
    assert authorization.principal_id == "browser-research"
    assert authorization.allow_global_sources is True


def test_search_empty_result(client):
    with patch(
        "app.services.research_service.KnowledgeRetrievalService.retrieve_with_agents",
        return_value=OrchestrationResult(
            status="no_relevant_results",
            results=(),
            partial=False,
        ),
    ):
        response = client.post(
            "/research/search",
            json={"query": "zzzz no match expected"},
        )
    assert response.status_code == 200
    payload = response.json()
    assert payload["retrieval_status"] == "empty"
    assert payload["results"] == []


def test_search_failure_normalized(client):
    with patch(
        "app.services.research_service.KnowledgeRetrievalService.retrieve_with_agents",
        return_value=OrchestrationResult(
            status="complete_failure",
            results=(),
            partial=False,
            failures=(
                AgentFailure(
                    code="embedding_unavailable",
                    message="Retrieval is temporarily unavailable.",
                    retriable=True,
                    error_class="TimeoutError",
                ),
            ),
        ),
    ):
        response = client.post(
            "/research/search",
            json={"query": "overtime"},
        )
    assert response.status_code == 200
    payload = response.json()
    assert payload["retrieval_status"] == "failed"
    assert payload["failures"][0]["message"] == "Retrieval is temporarily unavailable."
    assert "Traceback" not in json.dumps(payload)


def test_search_provider_exception_safe(client):
    with patch(
        "app.services.research_service.KnowledgeRetrievalService.retrieve_with_agents",
        side_effect=RuntimeError("secret db url postgresql://user:pass@host/db"),
    ):
        response = client.post("/research/search", json={"query": "overtime"})
    assert response.status_code == 503
    assert response.json()["detail"] == "Retrieval is temporarily unavailable."
    assert "postgresql" not in response.text.lower()
    assert "pass@" not in response.text


def test_search_clamps_and_rejects_oversized_limits(client):
    with patch(
        "app.services.research_service.KnowledgeRetrievalService.retrieve_with_agents",
        return_value=OrchestrationResult(status="success", results=()),
    ) as mock_retrieve:
        response = client.post(
            "/research/search",
            json={"query": "overtime", "limit": 24, "limit_per_source": 5},
        )
    assert response.status_code == 200
    assert mock_retrieve.call_args.kwargs["result_limit"] == 24
    assert mock_retrieve.call_args.kwargs["limit_per_source"] == 5

    oversized = client.post(
        "/research/search",
        json={"query": "overtime", "limit": 999, "limit_per_source": 99},
    )
    assert oversized.status_code == 422


def test_search_rejects_unsupported_source_type(client):
    response = client.post(
        "/research/search",
        json={"query": "overtime", "source_types": ["NOT_A_REAL_TYPE"]},
    )
    assert response.status_code == 400
    assert "Unsupported source_type" in response.json()["detail"]


def test_search_source_type_filter_forwarded(client):
    with patch(
        "app.services.research_service.KnowledgeRetrievalService.retrieve_with_agents",
        return_value=OrchestrationResult(status="success", results=()),
    ) as mock_retrieve:
        response = client.post(
            "/research/search",
            json={
                "query": "overtime",
                "source_types": ["contract", "cim"],
                "source_ids": ["contract-na"],
            },
        )
    assert response.status_code == 200
    assert mock_retrieve.call_args.kwargs["source_types"] == ("CONTRACT", "CIM")
    assert mock_retrieve.call_args.kwargs["source_ids"] == ("contract-na",)


def test_search_ignores_browser_api_key_as_authority(client, auth_env):
    del auth_env
    with patch(
        "app.services.research_service.KnowledgeRetrievalService.retrieve_with_agents",
        return_value=OrchestrationResult(status="success", results=()),
    ) as mock_retrieve:
        response = client.post(
            "/research/search",
            json={"query": "overtime"},
            headers={"X-API-Key": ADMIN_KEY, "Authorization": f"Bearer {READ_KEY}"},
        )
    assert response.status_code == 200
    authorization = mock_retrieve.call_args.args[2]
    assert authorization.principal_id == "browser-research"
    assert authorization.is_admin is False
    assert authorization.allow_all_organizations is False


def test_protected_sources_still_require_auth(client, auth_env):
    del auth_env
    denied = client.get("/sources/")
    assert denied.status_code == 401
    allowed = client.get("/sources/", headers={"X-API-Key": READ_KEY})
    assert allowed.status_code == 200


def test_research_routes_are_read_only():
    schema = app.openapi()
    research_paths = {
        path: sorted(methods)
        for path, methods in schema.get("paths", {}).items()
        if path.startswith("/research")
    }
    assert "/research/meta" in research_paths
    assert "get" in research_paths["/research/meta"]
    assert "/research/sources" in research_paths
    assert "get" in research_paths["/research/sources"]
    assert "/research/sources/{source_document_id}" in research_paths
    assert "get" in research_paths["/research/sources/{source_document_id}"]
    assert "/research/passages/{source_chunk_id}" in research_paths
    assert "get" in research_paths["/research/passages/{source_chunk_id}"]
    assert "/research/search" in research_paths
    assert "post" in research_paths["/research/search"]
    mutating = {
        method
        for methods in research_paths.values()
        for method in methods
        if method in {"put", "patch", "delete"}
    }
    assert mutating == set()


def test_list_and_detail_endpoints(client):
    list_payload = ResearchSourceListResponse(
        count=0,
        total=0,
        limit=50,
        offset=0,
        sources=[],
        authority_notice=AUTHORITY_NOTICE,
    )
    detail = ResearchSourceDetail(
        source_document_id=1,
        canonical_source_id="x",
        title="T",
        source_type="ELM",
        source_type_label=SOURCE_TYPE_LABELS["ELM"],
        is_current=True,
        processing_status="processed",
        is_indexed=True,
        chunk_count=1,
        embedded_chunk_count=1,
        authority_notice=AUTHORITY_NOTICE,
    )
    passage = ResearchPassageDetail(
        source_chunk_id=55,
        chunk_index=2,
        source_document_id=7,
        canonical_source_id="cim-v6",
        source_title="CIM v6",
        source_type="CIM",
        source_type_label=SOURCE_TYPE_LABELS["CIM"],
        page_number=4,
        section_label="Art. 8",
        passage_text="Section text about discipline.",
        processing_status="processed",
        is_indexed=True,
        authority_notice=AUTHORITY_NOTICE,
    )
    with patch(
        "app.api.routes.research.ResearchService.list_sources",
        return_value=list_payload,
    ):
        listed = client.get("/research/sources?limit=50&offset=0")
    assert listed.status_code == 200
    assert listed.json()["authority_notice"] == AUTHORITY_NOTICE

    with patch(
        "app.api.routes.research.ResearchService.get_source",
        return_value=detail,
    ):
        detailed = client.get("/research/sources/1")
    assert detailed.status_code == 200
    body = detailed.json()
    assert body["source_type"] == "ELM"
    assert "local_path" not in body
    assert "sha256" not in body
    assert "embedding" not in body

    with patch(
        "app.api.routes.research.ResearchService.get_passage",
        return_value=passage,
    ):
        passage_response = client.get("/research/passages/55")
    assert passage_response.status_code == 200
    assert "embedding" not in passage_response.json()
    assert "local_path" not in json.dumps(passage_response.json())


def test_source_detail_404(client):
    with patch(
        "app.api.routes.research.ResearchService.get_source",
        side_effect=ResearchNotFoundError("Source document not found."),
    ):
        response = client.get("/research/sources/999999")
    assert response.status_code == 404


def test_search_pagination_offset(client):
    results = tuple(
        _evidence(
            chunk_id=100 + i,
            chunk_index=i,
            chunk_text=f"Passage {i}",
            final_relevance_score=0.9 - (i * 0.01),
        )
        for i in range(5)
    )
    with patch(
        "app.services.research_service.KnowledgeRetrievalService.retrieve_with_agents",
        return_value=OrchestrationResult(status="success", results=results),
    ) as mock_retrieve:
        response = client.post(
            "/research/search",
            json={"query": "passage", "limit": 2, "offset": 2},
        )
    assert response.status_code == 200
    payload = response.json()
    assert payload["result_count"] == 2
    assert payload["total_matched"] == 5
    assert payload["offset"] == 2
    assert payload["results"][0]["passage_text"] == "Passage 2"
    assert mock_retrieve.call_args.kwargs["result_limit"] == 4


def test_map_retrieval_ui_status_values():
    assert map_retrieval_ui_status("success", result_count=1, partial=False) == "ok"
    assert map_retrieval_ui_status("success", result_count=0, partial=False) == "empty"
    assert (
        map_retrieval_ui_status("no_relevant_results", result_count=0, partial=False)
        == "empty"
    )
    assert (
        map_retrieval_ui_status("complete_failure", result_count=0, partial=False)
        == "failed"
    )
    assert (
        map_retrieval_ui_status("partial_failure", result_count=1, partial=True)
        == "partial"
    )


def test_search_request_model_bounds():
    ok = ResearchSearchRequest(query="  overtime  ", limit=12)
    assert ok.query == "overtime"
    with pytest.raises(Exception):
        ResearchSearchRequest(query="   ")
    with pytest.raises(Exception):
        ResearchSearchRequest(query="x", limit=100)


def test_search_does_not_call_case_mutation_services(client):
    with patch(
        "app.services.research_service.KnowledgeRetrievalService.retrieve_with_agents",
        return_value=OrchestrationResult(status="success", results=()),
    ):
        with patch("app.services.case_service.CaseService.create_case") as create_case:
            with patch(
                "app.services.case_memory_service.CaseMemoryService.record_outcome"
            ) as record_outcome:
                with patch(
                    "app.services.source_processing_service.SourceProcessingService.process_source"
                ) as process_source:
                    response = client.post(
                        "/research/search",
                        json={"query": "overtime"},
                    )
    assert response.status_code == 200
    create_case.assert_not_called()
    record_outcome.assert_not_called()
    process_source.assert_not_called()


def test_response_models_forbid_secret_fields():
    item_fields = set(ResearchSearchResultItem.model_fields)
    forbidden = {
        "embedding",
        "local_path",
        "final_url",
        "sha256",
        "source_sha256",
        "organization_id",
        "processing_error",
        "raw_vector_distance",
        "database_url",
        "api_key",
    }
    assert forbidden.isdisjoint(item_fields)


def test_result_projection_strips_unsafe_metadata_keys():
    item = ResearchService._result_item(_evidence(), rank=1)
    dumped = item.model_dump()
    assert dumped["metadata"]["article"] == "16"
    assert "local_path" not in dumped["metadata"]
    assert "embedding" not in dumped["metadata"]
    assert dumped["excerpt"]
