from unittest.mock import MagicMock
import services.llm_service as llm_service_module


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


def _tool_chunk(call_id: str, fn_name: str, arguments: str, idx: int = 0):
    """Single tool call delta chunk at the given index."""
    chunk = MagicMock()
    tc = MagicMock()
    tc.id = call_id
    tc.index = idx
    tc.function.name = fn_name
    tc.function.arguments = arguments
    delta = MagicMock()
    delta.content = None
    delta.tool_calls = [tc]
    chunk.choices = [MagicMock(delta=delta, finish_reason=None)]
    return chunk


def _partial_args_chunk(arguments: str, idx: int = 0):
    """Continuation chunk: no id/name, just more argument bytes at the given index."""
    chunk = MagicMock()
    tc = MagicMock()
    tc.id = None
    tc.index = idx
    tc.function.name = None
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


MESSAGES = [{"role": "user", "content": "What is the capital of France?"}]
_NO_OP_SUB_AGENT = MagicMock(return_value=iter([]))


# ---------------------------------------------------------------------------
# Existing tests (updated for new signature + typed-dict yields)
# ---------------------------------------------------------------------------

def test_direct_response_yields_text(monkeypatch):
    """When the LLM responds with text (no tool call), all deltas are yielded as typed dicts."""
    mock_client = MagicMock()
    mock_client.chat.completions.create.return_value = iter([
        _text_chunk("Paris"),
        _text_chunk(" is the capital."),
        _empty_chunk(),
    ])
    monkeypatch.setattr(llm_service_module, "_client", mock_client)

    results = list(llm_service_module.stream_chat_response(
        messages=MESSAGES,
        retrieval_fn=lambda q, mf=None: "irrelevant",
        sub_agent_fn=MagicMock(return_value=iter([])),
        text_to_sql_fn=MagicMock(return_value=("", "")),
        web_search_fn=MagicMock(return_value=""),
        user_id="user-1",
    ))

    assert results == [
        {"type": "delta", "delta": "Paris"},
        {"type": "delta", "delta": " is the capital."},
    ]
    assert mock_client.chat.completions.create.call_count == 1


def test_tool_call_triggers_retrieval_and_second_pass(monkeypatch):
    """When the LLM calls retrieve_chunks, retrieval_fn is invoked and Pass 2 streams."""
    mock_client = MagicMock()

    pass1 = iter([
        _tool_chunk("call_abc", "retrieve_chunks", '{"query": "capital of France"}'),
        _empty_chunk(),
    ])
    pass2 = iter([
        _text_chunk("Paris is the capital of France."),
        _empty_chunk(),
    ])
    mock_client.chat.completions.create.side_effect = [pass1, pass2]
    monkeypatch.setattr(llm_service_module, "_client", mock_client)

    retrieval_fn = MagicMock(return_value="Context: France's capital is Paris.")

    results = list(llm_service_module.stream_chat_response(
        messages=MESSAGES,
        retrieval_fn=retrieval_fn,
        sub_agent_fn=MagicMock(return_value=iter([])),
        text_to_sql_fn=MagicMock(return_value=("", "")),
        web_search_fn=MagicMock(return_value=""),
        user_id="user-1",
    ))

    retrieval_fn.assert_called_once_with("capital of France", None)
    deltas = [e["delta"] for e in results if e["type"] == "delta"]
    assert deltas == ["Paris is the capital of France."]
    assert mock_client.chat.completions.create.call_count == 2


def test_no_text_yielded_during_tool_call_phase(monkeypatch):
    """During the tool-call phase only typed event dicts are yielded — no delta events."""
    mock_client = MagicMock()

    pass1 = iter([
        _tool_chunk("call_xyz", "retrieve_chunks", '{"query": "test"}'),
        _empty_chunk(),
    ])
    pass2 = iter([_text_chunk("Answer"), _empty_chunk()])
    mock_client.chat.completions.create.side_effect = [pass1, pass2]
    monkeypatch.setattr(llm_service_module, "_client", mock_client)

    results = list(llm_service_module.stream_chat_response(
        messages=MESSAGES,
        retrieval_fn=lambda q, mf=None: "ctx",
        sub_agent_fn=MagicMock(return_value=iter([])),
        text_to_sql_fn=MagicMock(return_value=("", "")),
        web_search_fn=MagicMock(return_value=""),
        user_id="user-1",
    ))

    # Only the Pass-2 text should appear as a delta
    deltas = [e["delta"] for e in results if e["type"] == "delta"]
    assert deltas == ["Answer"]


# ---------------------------------------------------------------------------
# New tests
# ---------------------------------------------------------------------------

def test_agentic_loop_tool_then_response(monkeypatch):
    """Typed event order: tool_call_start → tool_call_end → delta."""
    mock_client = MagicMock()
    pass1 = iter([_tool_chunk("c1", "retrieve_chunks", '{"query": "paris"}'), _empty_chunk()])
    pass2 = iter([_text_chunk("Paris."), _empty_chunk()])
    mock_client.chat.completions.create.side_effect = [pass1, pass2]
    monkeypatch.setattr(llm_service_module, "_client", mock_client)

    results = list(llm_service_module.stream_chat_response(
        messages=MESSAGES,
        retrieval_fn=MagicMock(return_value="ctx"),
        sub_agent_fn=MagicMock(return_value=iter([])),
        text_to_sql_fn=MagicMock(return_value=("", "")),
        web_search_fn=MagicMock(return_value=""),
        user_id="user-1",
    ))

    types = [e["type"] for e in results]
    assert types == ["tool_call_start", "tool_call_end", "delta"]


def test_two_tools_in_one_turn(monkeypatch):
    """Two retrieve_chunks calls in one turn produce two start/end pairs; retrieval_fn called twice."""
    mock_client = MagicMock()
    pass1 = iter([
        _tool_chunk("call_a", "retrieve_chunks", '{"query": "first"}', idx=0),
        _tool_chunk("call_b", "retrieve_chunks", '{"query": "second"}', idx=1),
        _empty_chunk(),
    ])
    pass2 = iter([_text_chunk("Both retrieved."), _empty_chunk()])
    mock_client.chat.completions.create.side_effect = [pass1, pass2]
    monkeypatch.setattr(llm_service_module, "_client", mock_client)

    retrieval_fn = MagicMock(return_value="ctx")
    results = list(llm_service_module.stream_chat_response(
        messages=MESSAGES,
        retrieval_fn=retrieval_fn,
        sub_agent_fn=MagicMock(return_value=iter([])),
        text_to_sql_fn=MagicMock(return_value=("", "")),
        web_search_fn=MagicMock(return_value=""),
        user_id="user-1",
    ))

    types = [e["type"] for e in results]
    assert types.count("tool_call_start") == 2
    assert types.count("tool_call_end") == 2
    assert retrieval_fn.call_count == 2


def test_spawn_sub_agent_dispatches(monkeypatch):
    """spawn_sub_agent tool call delegates to sub_agent_fn and yields sub_agent_start/delta/end."""
    mock_client = MagicMock()
    pass1 = iter([
        _tool_chunk("sa_1", "spawn_sub_agent", '{"task": "summarize", "document_name": "doc.pdf"}'),
        _empty_chunk(),
    ])
    pass2 = iter([_text_chunk("Summary done."), _empty_chunk()])
    mock_client.chat.completions.create.side_effect = [pass1, pass2]
    monkeypatch.setattr(llm_service_module, "_client", mock_client)

    sub_agent_fn = MagicMock(return_value=iter([
        {"type": "sub_agent_delta", "delta": "analysed content"},
    ]))

    results = list(llm_service_module.stream_chat_response(
        messages=MESSAGES,
        retrieval_fn=MagicMock(return_value="ctx"),
        sub_agent_fn=sub_agent_fn,
        text_to_sql_fn=MagicMock(return_value=("", "")),
        web_search_fn=MagicMock(return_value=""),
        user_id="user-1",
    ))

    types = [e["type"] for e in results]
    assert "sub_agent_start" in types
    assert "sub_agent_delta" in types
    assert "sub_agent_end" in types
    # Correct order
    assert types.index("sub_agent_start") < types.index("sub_agent_delta")
    assert types.index("sub_agent_delta") < types.index("sub_agent_end")
    sub_agent_fn.assert_called_once_with("summarize", "doc.pdf")


def test_all_yields_are_typed_dicts(monkeypatch):
    """stream_chat_response must never yield plain strings — only typed dicts."""
    mock_client = MagicMock()
    mock_client.chat.completions.create.return_value = iter([
        _text_chunk("Hello"),
        _text_chunk(" world"),
        _empty_chunk(),
    ])
    monkeypatch.setattr(llm_service_module, "_client", mock_client)

    results = list(llm_service_module.stream_chat_response(
        messages=MESSAGES,
        retrieval_fn=MagicMock(return_value="ctx"),
        sub_agent_fn=MagicMock(return_value=iter([])),
        text_to_sql_fn=MagicMock(return_value=("", "")),
        web_search_fn=MagicMock(return_value=""),
        user_id="user-1",
    ))

    for item in results:
        assert isinstance(item, dict), f"Expected dict, got {type(item)}: {item!r}"
        assert "type" in item


def test_args_accumulation_across_chunks(monkeypatch):
    """Arguments split across multiple chunks are assembled before JSON-parsing."""
    mock_client = MagicMock()
    # Three chunks building up '{"query": "test"}'
    pass1 = iter([
        _tool_chunk("c1", "retrieve_chunks", '{"quer'),
        _partial_args_chunk('y": "te'),
        _partial_args_chunk('st"}'),
        _empty_chunk(),
    ])
    pass2 = iter([_text_chunk("Result."), _empty_chunk()])
    mock_client.chat.completions.create.side_effect = [pass1, pass2]
    monkeypatch.setattr(llm_service_module, "_client", mock_client)

    retrieval_fn = MagicMock(return_value="ctx")
    list(llm_service_module.stream_chat_response(
        messages=MESSAGES,
        retrieval_fn=retrieval_fn,
        sub_agent_fn=MagicMock(return_value=iter([])),
        text_to_sql_fn=MagicMock(return_value=("", "")),
        web_search_fn=MagicMock(return_value=""),
        user_id="user-1",
    ))

    retrieval_fn.assert_called_once_with("test", None)


def test_max_iterations_guard(monkeypatch):
    """Loop terminates after MAX_ITERATIONS even when LLM always returns tool calls."""
    mock_client = MagicMock()

    def always_tool(*_args, **_kwargs):
        return iter([_tool_chunk("c1", "retrieve_chunks", '{"query": "q"}'), _empty_chunk()])

    mock_client.chat.completions.create.side_effect = always_tool
    monkeypatch.setattr(llm_service_module, "_client", mock_client)

    list(llm_service_module.stream_chat_response(
        messages=MESSAGES,
        retrieval_fn=MagicMock(return_value="ctx"),
        sub_agent_fn=MagicMock(return_value=iter([])),
        text_to_sql_fn=MagicMock(return_value=("", "")),
        web_search_fn=MagicMock(return_value=""),
        user_id="user-1",
    ))

    assert mock_client.chat.completions.create.call_count <= llm_service_module.MAX_ITERATIONS


# ---------------------------------------------------------------------------
# New tool tests: text_to_sql and web_search
# ---------------------------------------------------------------------------

def test_text_to_sql_tool_call(monkeypatch):
    """LLM returns text_to_sql tool call; assert tool_call_start + tool_call_end; text_to_sql_fn called."""
    mock_client = MagicMock()
    pass1 = iter([
        _tool_chunk("sql_1", "text_to_sql", '{"query": "how many docs?"}'),
        _empty_chunk(),
    ])
    pass2 = iter([_text_chunk("You have 3 documents."), _empty_chunk()])
    mock_client.chat.completions.create.side_effect = [pass1, pass2]
    monkeypatch.setattr(llm_service_module, "_client", mock_client)

    text_to_sql_fn = MagicMock(return_value=("SELECT id, name FROM documents WHERE user_id = 'user-1'", "id | name\n---\n1 | doc.pdf"))

    results = list(llm_service_module.stream_chat_response(
        messages=MESSAGES,
        retrieval_fn=MagicMock(return_value="ctx"),
        sub_agent_fn=MagicMock(return_value=iter([])),
        text_to_sql_fn=text_to_sql_fn,
        web_search_fn=MagicMock(return_value=""),
        user_id="user-1",
    ))

    types = [e["type"] for e in results]
    assert "tool_call_start" in types
    assert "tool_call_end" in types
    tool_start = next(e for e in results if e["type"] == "tool_call_start")
    assert tool_start["tool"] == "text_to_sql"
    text_to_sql_fn.assert_called_once_with("how many docs?")


def test_web_search_tool_call(monkeypatch):
    """LLM returns web_search tool call; assert tool_call_start + tool_call_end; web_search_fn called."""
    mock_client = MagicMock()
    pass1 = iter([
        _tool_chunk("ws_1", "web_search", '{"query": "python news"}'),
        _empty_chunk(),
    ])
    pass2 = iter([_text_chunk("Here is the latest Python news."), _empty_chunk()])
    mock_client.chat.completions.create.side_effect = [pass1, pass2]
    monkeypatch.setattr(llm_service_module, "_client", mock_client)

    web_search_fn = MagicMock(return_value="Python 3.12 released.")

    results = list(llm_service_module.stream_chat_response(
        messages=MESSAGES,
        retrieval_fn=MagicMock(return_value="ctx"),
        sub_agent_fn=MagicMock(return_value=iter([])),
        text_to_sql_fn=MagicMock(return_value=("", "")),
        web_search_fn=web_search_fn,
        user_id="user-1",
    ))

    types = [e["type"] for e in results]
    assert "tool_call_start" in types
    assert "tool_call_end" in types
    tool_start = next(e for e in results if e["type"] == "tool_call_start")
    assert tool_start["tool"] == "web_search"
    web_search_fn.assert_called_once_with("python news")


def test_text_to_sql_result_passed_back_to_llm(monkeypatch):
    """text_to_sql result appended as tool message with correct tool_call_id."""
    mock_client = MagicMock()
    pass1 = iter([
        _tool_chunk("sql_id_42", "text_to_sql", '{"query": "count docs"}'),
        _empty_chunk(),
    ])
    pass2 = iter([_text_chunk("Result."), _empty_chunk()])
    mock_client.chat.completions.create.side_effect = [pass1, pass2]
    monkeypatch.setattr(llm_service_module, "_client", mock_client)

    sql_result = "count\n---\n5"
    text_to_sql_fn = MagicMock(return_value=("SELECT count(*) FROM documents WHERE user_id = 'user-1'", sql_result))

    list(llm_service_module.stream_chat_response(
        messages=MESSAGES,
        retrieval_fn=MagicMock(return_value=""),
        sub_agent_fn=MagicMock(return_value=iter([])),
        text_to_sql_fn=text_to_sql_fn,
        web_search_fn=MagicMock(return_value=""),
        user_id="user-1",
    ))

    second_call_messages = mock_client.chat.completions.create.call_args_list[1][1]["messages"]
    tool_msgs = [m for m in second_call_messages if m.get("role") == "tool"]
    assert len(tool_msgs) == 1
    assert tool_msgs[0]["tool_call_id"] == "sql_id_42"
    assert tool_msgs[0]["content"] == sql_result


def test_web_search_result_passed_back_to_llm(monkeypatch):
    """web_search result appended as tool message with correct tool_call_id."""
    mock_client = MagicMock()
    pass1 = iter([
        _tool_chunk("ws_id_99", "web_search", '{"query": "current events"}'),
        _empty_chunk(),
    ])
    pass2 = iter([_text_chunk("Answer."), _empty_chunk()])
    mock_client.chat.completions.create.side_effect = [pass1, pass2]
    monkeypatch.setattr(llm_service_module, "_client", mock_client)

    search_result = "**News**\nURL: https://example.com\nContent here."
    web_search_fn = MagicMock(return_value=search_result)

    list(llm_service_module.stream_chat_response(
        messages=MESSAGES,
        retrieval_fn=MagicMock(return_value=""),
        sub_agent_fn=MagicMock(return_value=iter([])),
        text_to_sql_fn=MagicMock(return_value=("", "")),
        web_search_fn=web_search_fn,
        user_id="user-1",
    ))

    second_call_messages = mock_client.chat.completions.create.call_args_list[1][1]["messages"]
    tool_msgs = [m for m in second_call_messages if m.get("role") == "tool"]
    assert len(tool_msgs) == 1
    assert tool_msgs[0]["tool_call_id"] == "ws_id_99"
    assert tool_msgs[0]["content"] == search_result


def test_all_four_tools_registered(monkeypatch):
    """TEXT_TO_SQL_TOOL and WEB_SEARCH_TOOL present in tools list passed to API."""
    mock_client = MagicMock()
    mock_client.chat.completions.create.return_value = iter([
        _text_chunk("Hello"), _empty_chunk(),
    ])
    monkeypatch.setattr(llm_service_module, "_client", mock_client)

    list(llm_service_module.stream_chat_response(
        messages=MESSAGES,
        retrieval_fn=MagicMock(return_value=""),
        sub_agent_fn=MagicMock(return_value=iter([])),
        text_to_sql_fn=MagicMock(return_value=("", "")),
        web_search_fn=MagicMock(return_value=""),
        user_id="user-1",
    ))

    call_kwargs = mock_client.chat.completions.create.call_args_list[0][1]
    tool_names = [t["function"]["name"] for t in call_kwargs["tools"]]
    assert "text_to_sql" in tool_names
    assert "web_search" in tool_names
    assert "retrieve_chunks" in tool_names
    assert "spawn_sub_agent" in tool_names
