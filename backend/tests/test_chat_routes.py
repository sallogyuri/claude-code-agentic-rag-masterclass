from unittest.mock import MagicMock

TEST_USER_ID = "test-user-id"
THREAD_ID = "thread-123"


# ---------------------------------------------------------------------------
# GET /chat/threads
# ---------------------------------------------------------------------------

def test_list_threads_returns_data(client, mock_supabase):
    threads = [
        {"id": THREAD_ID, "title": "First chat", "created_at": "2024-01-01", "updated_at": "2024-01-01"}
    ]
    (
        mock_supabase.table.return_value
        .select.return_value
        .eq.return_value
        .order.return_value
        .execute.return_value
        .data
    ) = threads

    response = client.get("/chat/threads")
    assert response.status_code == 200
    assert response.json() == threads


# ---------------------------------------------------------------------------
# GET /chat/threads/{id}/messages
# ---------------------------------------------------------------------------

def test_list_messages_returns_messages(client, mock_supabase):
    thread_row = {"id": THREAD_ID}
    messages = [
        {"id": "msg-1", "role": "user", "content": "Hello", "created_at": "2024-01-01"},
        {"id": "msg-2", "role": "assistant", "content": "Hi", "created_at": "2024-01-01"},
    ]

    # First Supabase call: verify thread ownership (single())
    thread_execute = MagicMock()
    thread_execute.data = thread_row
    (
        mock_supabase.table.return_value
        .select.return_value
        .eq.return_value
        .eq.return_value
        .single.return_value
        .execute
    ).return_value = thread_execute

    # Second Supabase call: fetch messages (order())
    messages_execute = MagicMock()
    messages_execute.data = messages
    (
        mock_supabase.table.return_value
        .select.return_value
        .eq.return_value
        .order.return_value
        .execute
    ).return_value = messages_execute

    response = client.get(f"/chat/threads/{THREAD_ID}/messages")
    assert response.status_code == 200
    assert response.json() == messages


def test_list_messages_for_unowned_thread_returns_404(client, mock_supabase):
    thread_execute = MagicMock()
    thread_execute.data = None  # thread not found / not owned
    (
        mock_supabase.table.return_value
        .select.return_value
        .eq.return_value
        .eq.return_value
        .single.return_value
        .execute
    ).return_value = thread_execute

    response = client.get("/chat/threads/nonexistent-id/messages")
    assert response.status_code == 404


# ---------------------------------------------------------------------------
# POST /chat/stream
# ---------------------------------------------------------------------------

def _make_text_delta(content: str):
    chunk = MagicMock()
    delta = MagicMock()
    delta.content = content
    delta.tool_calls = None
    chunk.choices = [MagicMock(delta=delta, finish_reason=None)]
    return chunk


def _make_empty_chunk():
    chunk = MagicMock()
    chunk.choices = []
    return chunk


def _make_tool_chunk(call_id: str, fn_name: str, arguments: str):
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


def test_chat_stream_creates_new_thread_and_streams(client, mock_supabase, mock_openai, monkeypatch):
    """POST /chat/stream with no thread_id creates a thread and returns SSE deltas."""
    new_thread = {"id": THREAD_ID, "title": "New Chat", "user_id": TEST_USER_ID}

    # Thread insert → returns the new thread
    mock_supabase.table.return_value.insert.return_value.execute.return_value.data = [new_thread]

    # Load history: empty (no prior messages)
    mock_supabase.table.return_value.select.return_value.eq.return_value.order.return_value.execute.return_value.data = []

    # LLM: direct text response, no tool call
    stream_chunks = [_make_text_delta("Hello"), _make_text_delta(" there"), _make_empty_chunk()]
    mock_openai.chat.completions.create.return_value = iter(stream_chunks)

    response = client.post("/chat/stream", json={"message": "Hi"})
    assert response.status_code == 200
    assert "text/event-stream" in response.headers["content-type"]
    body = response.text
    assert "Hello" in body
    assert " there" in body
    assert '"type": "done"' in body  # typed done event in the final SSE line


def test_stream_emits_typed_delta(client, mock_supabase, mock_openai):
    """SSE body contains typed delta events with type=delta."""
    new_thread = {"id": THREAD_ID, "title": "New Chat", "user_id": TEST_USER_ID}
    mock_supabase.table.return_value.insert.return_value.execute.return_value.data = [new_thread]
    mock_supabase.table.return_value.select.return_value.eq.return_value.order.return_value.execute.return_value.data = []

    mock_openai.chat.completions.create.return_value = iter([
        _make_text_delta("typed answer"),
        _make_empty_chunk(),
    ])

    response = client.post("/chat/stream", json={"message": "Hello"})
    assert response.status_code == 200
    body = response.text
    assert '"type": "delta"' in body
    assert "typed answer" in body


def test_stream_sub_agent_events_forwarded(client, mock_supabase, mock_openai, mock_sub_agent):
    """When LLM calls spawn_sub_agent, sub-agent events appear in the SSE body."""
    new_thread = {"id": THREAD_ID, "title": "New Chat", "user_id": TEST_USER_ID}
    mock_supabase.table.return_value.insert.return_value.execute.return_value.data = [new_thread]
    mock_supabase.table.return_value.select.return_value.eq.return_value.order.return_value.execute.return_value.data = []

    # Pass 1: spawn_sub_agent tool call
    pass1 = iter([
        _make_tool_chunk("sa_1", "spawn_sub_agent", '{"task": "summarize", "document_name": "doc.pdf"}'),
        _make_empty_chunk(),
    ])
    # Pass 2: final text response
    pass2 = iter([_make_text_delta("Summary complete."), _make_empty_chunk()])
    mock_openai.chat.completions.create.side_effect = [pass1, pass2]

    # Sub-agent yields one delta
    mock_sub_agent.return_value = iter([{"type": "sub_agent_delta", "delta": "analysis result"}])

    response = client.post("/chat/stream", json={"message": "Summarise doc.pdf"})
    assert response.status_code == 200
    body = response.text
    assert '"type": "sub_agent_start"' in body
    assert '"type": "sub_agent_end"' in body
    assert "analysis result" in body


def test_stream_error_emits_typed_error(client, mock_supabase, mock_openai):
    """When the LLM raises, the SSE body contains a typed error event."""
    new_thread = {"id": THREAD_ID, "title": "New Chat", "user_id": TEST_USER_ID}
    mock_supabase.table.return_value.insert.return_value.execute.return_value.data = [new_thread]
    mock_supabase.table.return_value.select.return_value.eq.return_value.order.return_value.execute.return_value.data = []

    mock_openai.chat.completions.create.side_effect = RuntimeError("LLM unavailable")

    response = client.post("/chat/stream", json={"message": "Hi"})
    assert response.status_code == 200
    body = response.text
    assert '"type": "error"' in body
