"""Tests for reranking_service: LLM-based reranking with fallback."""
import sys
import os
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from services.reranking_service import rerank_chunks

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _chunk(content: str, doc: str = "doc.txt") -> dict:
    return {"chunk_id": "id", "content": content, "document_name": doc, "rrf_score": 0.5}


def _mock_llm_response(scores_json: str) -> MagicMock:
    """Build a mock openai response with the given JSON content."""
    msg = MagicMock()
    msg.content = scores_json
    choice = MagicMock()
    choice.message = msg
    resp = MagicMock()
    resp.choices = [choice]
    return resp


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_rerank_passthrough_when_lte_top_k():
    """No LLM call when len(chunks) <= top_k — returns chunks unchanged."""
    chunks = [_chunk("a"), _chunk("b"), _chunk("c")]
    with patch("services.reranking_service._client") as mock_client:
        result = rerank_chunks("query", chunks, top_k=5)
    mock_client.chat.completions.create.assert_not_called()
    assert result == chunks


def test_rerank_returns_top_k():
    """Returns at most top_k chunks after reranking."""
    chunks = [_chunk(f"text {i}") for i in range(8)]
    scores_json = '{"scores": [' + ", ".join(f'{{"index": {i}, "score": {i * 0.1}}}' for i in range(8)) + ']}'
    with patch("services.reranking_service._client") as mock_client:
        mock_client.chat.completions.create.return_value = _mock_llm_response(scores_json)
        result = rerank_chunks("query", chunks, top_k=3)
    assert len(result) == 3


def test_rerank_orders_by_score():
    """Chunk with highest LLM score comes first."""
    chunks = [_chunk("low"), _chunk("high"), _chunk("mid")]
    # index 1 (high) gets score 0.9, index 0 gets 0.1, index 2 gets 0.5
    scores_json = '{"scores": [{"index": 0, "score": 0.1}, {"index": 1, "score": 0.9}, {"index": 2, "score": 0.5}]}'
    with patch("services.reranking_service._client") as mock_client:
        mock_client.chat.completions.create.return_value = _mock_llm_response(scores_json)
        result = rerank_chunks("query", chunks, top_k=2)
    assert result[0]["content"] == "high"


def test_rerank_fallback_on_exception():
    """Returns chunks[:top_k] unmodified when LLM call raises an exception."""
    chunks = [_chunk(f"text {i}") for i in range(8)]
    with patch("services.reranking_service._client") as mock_client:
        mock_client.chat.completions.create.side_effect = RuntimeError("LLM error")
        result = rerank_chunks("query", chunks, top_k=3)
    assert result == chunks[:3]


def test_rerank_partial_scores():
    """Handles LLM returning fewer scores than input — missing chunks get score 0."""
    chunks = [_chunk("a"), _chunk("b"), _chunk("c"), _chunk("d"), _chunk("e"), _chunk("f")]
    # Only score index 2 and 0; rest default to 0
    scores_json = '{"scores": [{"index": 2, "score": 0.8}, {"index": 0, "score": 0.6}]}'
    with patch("services.reranking_service._client") as mock_client:
        mock_client.chat.completions.create.return_value = _mock_llm_response(scores_json)
        result = rerank_chunks("query", chunks, top_k=3)
    # index 2 (score 0.8) should be first, index 0 (0.6) second
    assert result[0]["content"] == "c"
    assert result[1]["content"] == "a"
