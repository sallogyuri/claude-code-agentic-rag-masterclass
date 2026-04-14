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
    chunk.choices = [MagicMock(delta=delta)]
    return chunk


def _make_empty_chunk():
    chunk = MagicMock()
    chunk.choices = []
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
    assert "true" in body  # done: true in the final SSE event
