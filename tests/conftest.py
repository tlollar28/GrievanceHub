import json
from pathlib import Path
from types import SimpleNamespace

import pytest


FIXTURES_DIR = Path(__file__).parent / "fixtures"


class MockSourceDocument:
    def __init__(self, name="NPMHU CIM v6", source_type="CIM"):
        self.name = name
        self.source_type = source_type


class MockSourceChunk:
    def __init__(self, text, chunk_index=0, page_number=1, source_type="CIM"):
        self.text = text
        self.chunk_index = chunk_index
        self.page_number = page_number
        self.source_document_id = 1
        self.source_document = MockSourceDocument(source_type=source_type)
        self.retrieval_metadata = {}


@pytest.fixture
def load_fixture():
    def _load(relative_path: str) -> dict:
        path = FIXTURES_DIR / relative_path
        return json.loads(path.read_text(encoding="utf-8"))

    return _load


@pytest.fixture
def annual_leave_fixture(load_fixture):
    return load_fixture("analysis/annual_leave_cancellation_analysis.json")


@pytest.fixture
def schedule_change_fixture(load_fixture):
    return load_fixture("analysis/schedule_change_analysis.json")


@pytest.fixture
def mock_chunk_factory():
    def _factory(text, chunk_index=0, page_number=1, source_type="CIM"):
        return MockSourceChunk(
            text=text,
            chunk_index=chunk_index,
            page_number=page_number,
            source_type=source_type,
        )

    return _factory
