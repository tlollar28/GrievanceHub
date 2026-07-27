"""Regression: indexed source-type helper must not instantiate abstract BaseProvider."""

from __future__ import annotations

from unittest.mock import MagicMock

from app.services.knowledge_retrieval_service import KnowledgeRetrievalService
from app.services.providers.base_provider import BaseProvider


def test_authorization_predicates_available_without_instantiation():
    predicates = BaseProvider._authorization_predicates(None)
    assert len(predicates) == 1


def test_get_indexed_source_types_does_not_use_abstract_new(monkeypatch):
    """Python 3.14+ raises TypeError on BaseProvider.__new__(BaseProvider)."""

    def boom(*_args, **_kwargs):
        raise TypeError(
            "Can't instantiate abstract class BaseProvider without an "
            "implementation for abstract method 'search'"
        )

    monkeypatch.setattr(BaseProvider, "__new__", boom)

    db = MagicMock()
    query = MagicMock()
    db.query.return_value = query
    query.join.return_value = query
    query.filter.return_value = query
    query.distinct.return_value = query
    query.all.return_value = [("CONTRACT",), ("CIM",)]

    result = KnowledgeRetrievalService._get_indexed_source_types(db)
    assert result == {"CONTRACT", "CIM"}
