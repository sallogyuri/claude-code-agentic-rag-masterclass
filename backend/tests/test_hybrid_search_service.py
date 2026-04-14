"""Tests for hybrid_search_service: RRF logic and hybrid_search integration."""
import sys
import os
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from services.hybrid_search_service import (
    _reciprocal_rank_fusion,
    hybrid_search,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _chunk(chunk_id: str, content: str = "text", doc: str = "doc.txt", score: float = 1.0) -> dict:
    return {"chunk_id": chunk_id, "content": content, "document_name": doc, "score": score}


# ---------------------------------------------------------------------------
# _reciprocal_rank_fusion
# ---------------------------------------------------------------------------

def test_rrf_both_lists():
    """A chunk appearing in both lists scores higher than one in only one list."""
    shared = _chunk("shared")
    vector_only = _chunk("vec-only")
    keyword_only = _chunk("kw-only")

    result = _reciprocal_rank_fusion([shared, vector_only], [shared, keyword_only])
    by_id = {r["chunk_id"]: r["rrf_score"] for r in result}

    assert by_id["shared"] > by_id["vec-only"]
    assert by_id["shared"] > by_id["kw-only"]


def test_rrf_vector_only():
    """Works correctly when keyword results are empty."""
    result = _reciprocal_rank_fusion([_chunk("a"), _chunk("b")], [])
    assert len(result) == 2
    assert result[0]["chunk_id"] == "a"  # position 1 beats position 2


def test_rrf_keyword_only():
    """Works correctly when vector results are empty."""
    result = _reciprocal_rank_fusion([], [_chunk("x"), _chunk("y")])
    assert len(result) == 2
    assert result[0]["chunk_id"] == "x"


def test_rrf_deduplication():
    """A chunk_id appearing in both lists produces only one output row."""
    chunk = _chunk("dup")
    result = _reciprocal_rank_fusion([chunk], [chunk])
    ids = [r["chunk_id"] for r in result]
    assert ids.count("dup") == 1


def test_rrf_ordering():
    """Results are sorted by RRF score descending."""
    vector = [_chunk("a"), _chunk("b"), _chunk("c")]
    keyword = [_chunk("c"), _chunk("b"), _chunk("a")]
    result = _reciprocal_rank_fusion(vector, keyword)
    scores = [r["rrf_score"] for r in result]
    assert scores == sorted(scores, reverse=True)


# ---------------------------------------------------------------------------
# hybrid_search integration (mock supabase)
# ---------------------------------------------------------------------------

def _make_supabase_mock(vector_rows: list[dict], keyword_rows: list[dict]) -> MagicMock:
    mock = MagicMock()

    def rpc_side_effect(fn_name, params):
        m = MagicMock()
        if fn_name == "match_chunks":
            m.execute.return_value.data = vector_rows
        else:
            m.execute.return_value.data = keyword_rows
        return m

    mock.rpc.side_effect = rpc_side_effect
    return mock


def test_hybrid_search_calls_both_rpcs():
    """hybrid_search calls both match_chunks and keyword_search_chunks RPCs."""
    sb = _make_supabase_mock([], [])
    with patch("services.hybrid_search_service.embed_text", return_value=[0.0] * 1536):
        hybrid_search("test query", "user-1", sb)

    rpc_calls = [call.args[0] for call in sb.rpc.call_args_list]
    assert "match_chunks" in rpc_calls
    assert "keyword_search_chunks" in rpc_calls


def test_hybrid_search_returns_top_n():
    """Result count is capped at candidate_count."""
    rows = [
        {"chunk_id": f"c{i}", "content": f"text {i}", "document_name": "doc.txt", "similarity": 0.9, "rank": 0.9}
        for i in range(20)
    ]
    sb = _make_supabase_mock(rows, rows)
    with patch("services.hybrid_search_service.embed_text", return_value=[0.0] * 1536):
        result = hybrid_search("query", "user-1", sb, candidate_count=5)

    assert len(result) <= 5
