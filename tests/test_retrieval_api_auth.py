"""API authentication and fail-closed authorization for source/retrieval routes."""

from __future__ import annotations

import inspect
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.api.auth import AuthenticatedPrincipal, authenticate_principal
from app.main import app
from app.services.knowledge_retrieval_service import KnowledgeRetrievalService
from app.services.retrieval.models import (
    OrchestrationResult,
    RetrievalAuthorizationContext,
)


READ_KEY = "test-read-key-not-for-production"
ADMIN_KEY = "test-admin-key-not-for-production"


@pytest.fixture
def auth_env(monkeypatch):
    monkeypatch.setenv("GRIEVANCEHUB_API_KEY", READ_KEY)
    monkeypatch.setenv("GRIEVANCEHUB_ADMIN_API_KEY", ADMIN_KEY)


@pytest.fixture
def client(auth_env):
    return TestClient(app)


def test_retrieve_with_agents_requires_authorization_argument():
    signature = inspect.signature(KnowledgeRetrievalService.retrieve_with_agents)
    parameters = list(signature.parameters)
    assert parameters[:3] == ["db", "query", "authorization"]
    assert signature.parameters["authorization"].default is inspect.Parameter.empty


def test_retrieve_with_agents_none_fails_closed_without_embedding():
    with patch(
        "app.services.embedding_service.EmbeddingService.create_embedding"
    ) as mock_embed:
        result = KnowledgeRetrievalService.retrieve_with_agents(
            MagicMock(),
            "contract article",
            None,
            domain="contract",
        )
    assert result.status == "authorization_failure"
    mock_embed.assert_not_called()


def test_search_with_agents_none_fails_closed():
    payload = KnowledgeRetrievalService.search_with_agents(
        MagicMock(),
        "contract article",
        None,
        domain="contract",
    )
    assert payload["retrieval_status"] == "authorization_failure"
    assert payload["results_by_source"]["CONTRACT"] == []


def test_retrieve_global_corpus_internal_is_explicit_and_trusted():
    with patch.object(
        KnowledgeRetrievalService,
        "retrieve_with_agents",
        return_value=OrchestrationResult(status="success"),
    ) as mock_retrieve:
        KnowledgeRetrievalService.retrieve_global_corpus_internal(
            MagicMock(),
            "supervisor step 1 meeting",
            principal_id="unit-test-internal",
            domain="supervisor_manual",
        )
    authorization = mock_retrieve.call_args.args[2]
    assert isinstance(authorization, RetrievalAuthorizationContext)
    assert authorization.authenticated is True
    assert authorization.principal_id == "unit-test-internal"
    assert authorization.allow_global_sources is True
    assert authorization.allow_all_organizations is False


def test_search_all_rejects_missing_authorization_type():
    with pytest.raises(TypeError):
        KnowledgeRetrievalService.search_all(MagicMock(), "question", None)


def test_authenticate_principal_rejects_missing_and_invalid(auth_env):
    with pytest.raises(Exception) as missing:
        authenticate_principal()
    assert missing.value.status_code == 401

    with pytest.raises(Exception) as invalid:
        authenticate_principal(x_api_key="wrong")
    assert invalid.value.status_code == 401


def test_authenticate_principal_read_and_admin(auth_env):
    read = authenticate_principal(authorization=f"Bearer {READ_KEY}")
    assert read.role == "read"
    assert read.retrieval_authorization().allow_all_organizations is False
    assert read.retrieval_authorization().is_admin is False

    admin = authenticate_principal(x_api_key=ADMIN_KEY)
    assert admin.role == "admin"
    # Retrieval scope remains global-only; admin role does not escalate corpus access.
    assert admin.retrieval_authorization().is_admin is False
    assert admin.retrieval_authorization().allow_all_organizations is False


def test_authenticate_admin_rejects_read_key(auth_env):
    with pytest.raises(Exception) as denied:
        authenticate_principal(x_api_key=READ_KEY, require_admin=True)
    assert denied.value.status_code == 403


def test_sources_search_requires_authentication(client):
    response = client.get("/sources/search/", params={"query": "article 10"})
    assert response.status_code == 401


def test_sources_search_rejects_invalid_credentials(client):
    response = client.get(
        "/sources/search/",
        params={"query": "article 10"},
        headers={"X-API-Key": "invalid"},
    )
    assert response.status_code == 401


def test_sources_search_uses_principal_bound_authorization(client):
    with patch.object(
        KnowledgeRetrievalService,
        "search_with_agents",
        return_value={
            "query": "article 10",
            "limit_per_source": 3,
            "results_by_source": {},
            "retrieval_status": "no_relevant_results",
            "partial": False,
            "failures": [],
        },
    ) as mock_search:
        response = client.get(
            "/sources/search/",
            params={"query": "article 10"},
            headers={"Authorization": f"Bearer {READ_KEY}"},
        )
    assert response.status_code == 200
    authorization = mock_search.call_args.kwargs["authorization"]
    assert authorization.authenticated is True
    assert authorization.allow_global_sources is True
    assert authorization.allowed_organization_ids == frozenset()
    assert authorization.allow_all_organizations is False
    assert authorization.is_admin is False


def test_sources_mutation_requires_admin(client):
    response = client.post(
        "/sources/seed-official/",
        headers={"Authorization": f"Bearer {READ_KEY}"},
    )
    assert response.status_code == 403


def test_sources_list_hides_local_path_for_read_principal(client):
    from app.database.session import get_db

    fake_source = MagicMock()
    fake_source.id = 1
    fake_source.source_id = "contract-1"
    fake_source.name = "Contract"
    fake_source.source_type = "CONTRACT"
    fake_source.official_page = None
    fake_source.download_url = None
    fake_source.local_path = "C:/secret/path.pdf"
    fake_source.sha256 = "abc"
    fake_source.is_current = True

    db = MagicMock()
    db.query.return_value.all.return_value = [fake_source]

    def _override_db():
        yield db

    app.dependency_overrides[get_db] = _override_db
    try:
        response = client.get(
            "/sources/",
            headers={"X-API-Key": READ_KEY},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    payload = response.json()
    assert payload["sources"][0]["source_id"] == "contract-1"
    assert "local_path" not in payload["sources"][0]


def test_caller_cannot_claim_admin_via_retrieval_context_builder():
    principal = AuthenticatedPrincipal(principal_id="api-read:test", role="read")
    context = principal.retrieval_authorization()
    assert context.is_admin is False
    assert context.allow_all_organizations is False
    assert context.allowed_organization_ids == frozenset()
