from unittest.mock import MagicMock
import services.llm_service as llm_service_module


def _text_chunk(content: str):
    chunk = MagicMock()
    delta = MagicMock()
    delta.content = content
    delta.tool_calls = None
    chunk.choices = [MagicMock(delta=delta)]
    return chunk


def _tool_chunk(call_id: str, fn_name: str, arguments: str):
    chunk = MagicMock()
    tc = MagicMock()
    tc.id = call_id
    tc.function.name = fn_name
    tc.function.arguments = arguments
    delta = MagicMock()
    delta.content = None
    delta.tool_calls = [tc]
    chunk.choices = [MagicMock(delta=delta)]
    return chunk


def _empty_chunk():
    chunk = MagicMock()
    chunk.choices = []
    return chunk


MESSAGES = [{"role": "user", "content": "What is the capital of France?"}]


def test_direct_response_yields_text(monkeypatch):
    """When the LLM responds with text (no tool call), all deltas are yielded."""
    mock_client = MagicMock()
    mock_client.chat.completions.create.return_value = iter([
        _text_chunk("Paris"),
        _text_chunk(" is the capital."),
        _empty_chunk(),
    ])
    monkeypatch.setattr(llm_service_module, "_client", mock_client)

    results = list(llm_service_module.stream_chat_response(
        messages=MESSAGES,
        retrieval_fn=lambda q: "irrelevant",
        user_id="user-1",
    ))

    assert results == ["Paris", " is the capital."]
    # Only one API call — no tool round-trip
    assert mock_client.chat.completions.create.call_count == 1


def test_tool_call_triggers_retrieval_and_second_pass(monkeypatch):
    """When the LLM calls retrieve_chunks, retrieval_fn is invoked and Pass 2 streams."""
    mock_client = MagicMock()

    # Pass 1: tool call
    pass1 = iter([
        _tool_chunk("call_abc", "retrieve_chunks", '{"query": "capital of France"}'),
        _empty_chunk(),
    ])
    # Pass 2: text answer
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
        user_id="user-1",
    ))

    retrieval_fn.assert_called_once_with("capital of France")
    assert results == ["Paris is the capital of France."]
    assert mock_client.chat.completions.create.call_count == 2


def test_no_text_yielded_during_tool_call_phase(monkeypatch):
    """Deltas during the tool-call phase must not leak into the output."""
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
        retrieval_fn=lambda q: "ctx",
        user_id="user-1",
    ))

    # No tool-phase content leaked; only Pass 2 text
    assert results == ["Answer"]
