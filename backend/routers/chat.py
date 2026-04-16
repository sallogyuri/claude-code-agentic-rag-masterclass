from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from supabase import create_client, Client
from config import settings, SYSTEM_PROMPT
from auth import get_current_user
from services.llm_service import stream_chat_response
from services.hybrid_search_service import hybrid_search
from services.reranking_service import rerank_chunks
from services.sub_agent_service import run_sub_agent_stream
from services.text_to_sql_service import text_to_sql
from services.web_search_service import web_search as web_search_svc
from typing import Iterator
import json

router = APIRouter()

supabase: Client = create_client(
    settings.supabase_url,
    settings.supabase_service_role_key,  # service role to write on behalf of user
)


class ChatRequest(BaseModel):
    message: str
    thread_id: str | None = None


def _get_or_create_thread(user_id: str, thread_id: str | None) -> dict:
    if thread_id:
        result = (
            supabase.table("threads")
            .select("*")
            .eq("id", thread_id)
            .eq("user_id", user_id)
            .single()
            .execute()
        )
        if not result.data:
            raise HTTPException(status_code=404, detail="Thread not found")
        return result.data

    result = (
        supabase.table("threads")
        .insert({"user_id": user_id, "title": "New Chat"})
        .execute()
    )
    return result.data[0]


def _save_message(thread_id: str, user_id: str, role: str, content: str) -> None:
    supabase.table("messages").insert({
        "thread_id": thread_id,
        "user_id": user_id,
        "role": role,
        "content": content,
    }).execute()


def _load_history(thread_id: str) -> list[dict]:
    result = (
        supabase.table("messages")
        .select("role, content")
        .eq("thread_id", thread_id)
        .order("created_at")
        .execute()
    )
    return [{"role": row["role"], "content": row["content"]} for row in result.data]


def _retrieve(
    query: str,
    user_id: str,
    metadata_filter: dict | None = None,
    document_name: str | None = None,
) -> str:
    candidates = hybrid_search(query, user_id, supabase, candidate_count=10, metadata_filter=metadata_filter)
    if document_name:
        candidates = [c for c in candidates if c.get("document_name") == document_name]
    top_chunks = rerank_chunks(query, candidates, top_k=5)

    if not top_chunks:
        return "No relevant documents found."

    parts = []
    for chunk in top_chunks:
        parts.append(f"[From: {chunk['document_name']}]\n{chunk['content']}")
    return "\n\n---\n\n".join(parts)


def _sse_generator(message: str, thread: dict, user_id: str):
    # Save user message first so it's included in history
    _save_message(thread["id"], user_id, "user", message)

    history = _load_history(thread["id"])
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        *history,
    ]

    retrieval_fn = lambda query, metadata_filter=None: _retrieve(query, user_id, metadata_filter)

    def sub_agent_fn(task: str, document_name: str) -> Iterator[dict]:
        scoped_fn = lambda q, mf=None: _retrieve(q, user_id, mf, document_name=document_name)
        yield from run_sub_agent_stream(task, document_name, user_id, scoped_fn)

    text_to_sql_fn = lambda query: text_to_sql(query, user_id)
    web_search_fn = lambda query: web_search_svc(query)

    full_response_parts: list[str] = []
    try:
        for event in stream_chat_response(messages, retrieval_fn, sub_agent_fn, text_to_sql_fn, web_search_fn, user_id):
            event_type = event.get("type")
            if event_type in ("delta", "sub_agent_delta"):
                full_response_parts.append(event["delta"])
            yield f"data: {json.dumps({**event, 'thread_id': thread['id']})}\n\n"
    except Exception as e:
        yield f"data: {json.dumps({'type': 'error', 'error': str(e), 'thread_id': thread['id']})}\n\n"
        return

    _save_message(thread["id"], user_id, "assistant", "".join(full_response_parts))

    if thread.get("title") == "New Chat":
        supabase.table("threads").update({"title": message[:60]}).eq("id", thread["id"]).execute()

    yield f"data: {json.dumps({'type': 'done', 'thread_id': thread['id']})}\n\n"


@router.post("/stream")
async def chat_stream(
    request: ChatRequest,
    user: dict = Depends(get_current_user),
):
    user_id = user["user_id"]
    thread = _get_or_create_thread(user_id, request.thread_id)

    return StreamingResponse(
        _sse_generator(request.message, thread, user_id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/threads")
def list_threads(user: dict = Depends(get_current_user)):
    result = (
        supabase.table("threads")
        .select("id, title, created_at, updated_at")
        .eq("user_id", user["user_id"])
        .order("updated_at", desc=True)
        .execute()
    )
    return result.data


@router.get("/threads/{thread_id}/messages")
def list_messages(thread_id: str, user: dict = Depends(get_current_user)):
    thread = (
        supabase.table("threads")
        .select("id")
        .eq("id", thread_id)
        .eq("user_id", user["user_id"])
        .single()
        .execute()
    )
    if not thread.data:
        raise HTTPException(status_code=404, detail="Thread not found")

    result = (
        supabase.table("messages")
        .select("id, role, content, created_at")
        .eq("thread_id", thread_id)
        .order("created_at")
        .execute()
    )
    return result.data
