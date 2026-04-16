from unittest.mock import MagicMock
import services.sub_agent_service as sub_agent_module

TASK = "Summarize the document"
DOC_NAME = "report.pdf"
USER_ID = "user-1"


# ---------------------------------------------------------------------------
# Chunk helpers
# ---------------------------------------------------------------------------

def _text_chunk(content: str):
    chunk = MagicMock()
    delta = MagicMock()
    delta.content = content
    delta.tool_calls = None
    chunk.choices = [MagicMock(delta=delta, finish_reason=None)]
    return chunk


def _tool_chunk(call_id: str, fn_name: str, arguments: str):
    chunk = MagicMock()
    tc = MagicMock()
    tc.id = call_id
    tc.index = 0
    tc.function.name = fn_name
    tc.function.arguments = arguments
    delta = MagicMock()
    delta.content = None
    delta.tool_calls = [tc]
    chunk.choices = [MagicMock(delta=delta, finish_reason=None)]
    return chunk


def _empty_chunk():
    chunk = MagicMock()
    chunk.choices = []
    return chunk


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_direct_response_yields_delta(monkeypatch):
    """Text-only response yields sub_agent_delta events."""
    mock_client = MagicMock()
    mock_client.chat.completions.create.return_value = iter([
        _text_chunk("Summary here."),
        _empty_chunk(),
    ])
    monkeypatch.setattr(sub_agent_module, "_client", mock_client)

    retrieval_fn = MagicMock(return_value="context")
    results = list(sub_agent_module.run_sub_agent_stream(TASK, DOC_NAME, USER_ID, retrieval_fn))

    assert results == [{"type": "sub_agent_delta", "delta": "Summary here."}]
    retrieval_fn.assert_not_called()


def test_tool_call_then_response(monkeypatch):
    """One retrieve_chunks call followed by text yields sub_agent_tool_call then sub_agent_delta."""
    mock_client = MagicMock()
    pass1 = iter([_tool_chunk("call_1", "retrieve_chunks", '{"query": "main findings"}'), _empty_chunk()])
    pass2 = iter([_text_chunk("The findings are..."), _empty_chunk()])
    mock_client.chat.completions.create.side_effect = [pass1, pass2]
    monkeypatch.setattr(sub_agent_module, "_client", mock_client)

    retrieval_fn = MagicMock(return_value="relevant context")
    results = list(sub_agent_module.run_sub_agent_stream(TASK, DOC_NAME, USER_ID, retrieval_fn))

    types = [e["type"] for e in results]
    assert "sub_agent_tool_call" in types
    assert "sub_agent_delta" in types
    # tool_call must precede delta
    assert types.index("sub_agent_tool_call") < types.index("sub_agent_delta")


def test_retrieval_fn_called_with_query(monkeypatch):
    """retrieval_fn receives the correct query and metadata_filter."""
    mock_client = MagicMock()
    pass1 = iter([_tool_chunk("c1", "retrieve_chunks", '{"query": "key points"}'), _empty_chunk()])
    pass2 = iter([_text_chunk("answer"), _empty_chunk()])
    mock_client.chat.completions.create.side_effect = [pass1, pass2]
    monkeypatch.setattr(sub_agent_module, "_client", mock_client)

    retrieval_fn = MagicMock(return_value="ctx")
    list(sub_agent_module.run_sub_agent_stream(TASK, DOC_NAME, USER_ID, retrieval_fn))

    retrieval_fn.assert_called_once_with("key points", None)


def test_max_iterations_guard(monkeypatch):
    """Loop terminates after MAX_SUB_AGENT_ITERATIONS even if LLM keeps calling tools."""
    mock_client = MagicMock()

    def always_tool_call():
        return iter([_tool_chunk("c1", "retrieve_chunks", '{"query": "q"}'), _empty_chunk()])

    mock_client.chat.completions.create.side_effect = always_tool_call
    monkeypatch.setattr(sub_agent_module, "_client", mock_client)

    retrieval_fn = MagicMock(return_value="ctx")
    list(sub_agent_module.run_sub_agent_stream(TASK, DOC_NAME, USER_ID, retrieval_fn))

    assert mock_client.chat.completions.create.call_count <= sub_agent_module.MAX_SUB_AGENT_ITERATIONS


def test_no_recursion(monkeypatch):
    """spawn_sub_agent tool must NOT be in the tools list passed to the API."""
    mock_client = MagicMock()
    mock_client.chat.completions.create.return_value = iter([_text_chunk("done"), _empty_chunk()])
    monkeypatch.setattr(sub_agent_module, "_client", mock_client)

    list(sub_agent_module.run_sub_agent_stream(TASK, DOC_NAME, USER_ID, MagicMock(return_value="")))

    call_kwargs = mock_client.chat.completions.create.call_args
    tools_used = call_kwargs.kwargs["tools"]
    tool_names = [t["function"]["name"] for t in tools_used]
    assert "spawn_sub_agent" not in tool_names
    assert "retrieve_chunks" in tool_names


def test_exception_yields_error_delta(monkeypatch):
    """If the LLM raises, an error delta is yielded and no exception propagates."""
    mock_client = MagicMock()
    mock_client.chat.completions.create.side_effect = RuntimeError("API failure")
    monkeypatch.setattr(sub_agent_module, "_client", mock_client)

    results = list(sub_agent_module.run_sub_agent_stream(TASK, DOC_NAME, USER_ID, MagicMock()))

    assert len(results) == 1
    assert results[0]["type"] == "sub_agent_delta"
    assert "Sub-agent error" in results[0]["delta"]
    assert "API failure" in results[0]["delta"]
