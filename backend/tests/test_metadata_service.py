import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from unittest.mock import MagicMock
import services.metadata_service as metadata_module
from services.metadata_service import extract_metadata, DocumentMetadata


def _make_mock_client(content: str):
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.choices[0].message.content = content
    mock_client.chat.completions.create.return_value = mock_response
    return mock_client


def test_extract_metadata_returns_populated_model(monkeypatch):
    payload = (
        '{"title": "Q4 Report", "summary": "A quarterly report.", '
        '"document_type": "report", "topics": ["finance", "earnings"], '
        '"language": "en", "author": "Acme Corp", "date": "2024-12-31"}'
    )
    monkeypatch.setattr(metadata_module, "_client", _make_mock_client(payload))

    result = extract_metadata("Some document text")

    assert result.title == "Q4 Report"
    assert result.summary == "A quarterly report."
    assert result.document_type == "report"
    assert result.topics == ["finance", "earnings"]
    assert result.language == "en"
    assert result.author == "Acme Corp"
    assert result.date == "2024-12-31"


def test_extract_metadata_handles_partial_json(monkeypatch):
    payload = '{"title": "Partial Doc", "summary": null, "document_type": null, "topics": null, "language": null, "author": null, "date": null}'
    monkeypatch.setattr(metadata_module, "_client", _make_mock_client(payload))

    result = extract_metadata("Some document text")

    assert result.title == "Partial Doc"
    assert result.summary is None
    assert result.document_type is None
    assert result.topics is None


def test_extract_metadata_returns_empty_on_llm_failure(monkeypatch):
    mock_client = MagicMock()
    mock_client.chat.completions.create.side_effect = Exception("LLM unavailable")
    monkeypatch.setattr(metadata_module, "_client", mock_client)

    result = extract_metadata("Some document text")

    assert isinstance(result, DocumentMetadata)
    assert result.title is None
    assert result.summary is None
    assert result.document_type is None


def test_extract_metadata_handles_invalid_json(monkeypatch):
    monkeypatch.setattr(metadata_module, "_client", _make_mock_client("not valid json at all"))

    result = extract_metadata("Some document text")

    assert isinstance(result, DocumentMetadata)
    assert result.title is None


def test_model_dump_excludes_none_fields():
    meta = DocumentMetadata(title="My Doc", summary=None, document_type="report", topics=None)
    dumped = meta.model_dump(exclude_none=True)

    assert "title" in dumped
    assert "document_type" in dumped
    assert "summary" not in dumped
    assert "topics" not in dumped
