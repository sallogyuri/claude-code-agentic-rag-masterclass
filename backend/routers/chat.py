from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from supabase import create_client, Client
from config import settings
from auth import get_current_user
from services.langsmith_service import traced_stream_response
import json

router = APIRouter()

supabase: Client = create_client(
    settings.supabase_url,
    settings.supabase_service_role_key,  # service role to write on behalf of user
)


class ChatRequest(BaseModel):
    message: str
    thread_id: str | None = None   # our internal UUID (not OpenAI thread ID)


def _get_or_create_thread(user_id: str, thread_id: str | None) -> dict:
    """
    Look up or create a threads row. Returns the full thread dict
    including the openai_thread_id.
    """
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

    # Create new OpenAI thread
    from openai import OpenAI
    from config import settings as cfg
    oai = OpenAI(api_key=cfg.openai_api_key)
    oai_thread = oai.beta.threads.create()

    result = (
        supabase.table("threads")
        .insert({
            "user_id": user_id,
            "title": "New Chat",
            "openai_thread_id": oai_thread.id,
        })
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


def _sse_generator(message: str, thread: dict, user_id: str):
    """Yields SSE-formatted text chunks, then a [DONE] sentinel."""
    full_response = []

    # Save user message
    _save_message(thread["id"], user_id, "user", message)

    try:
        for chunk in traced_stream_response(
            openai_thread_id=thread["openai_thread_id"],
            user_message=message,
            user_id=user_id,
        ):
            full_response.append(chunk)
            data = json.dumps({"delta": chunk, "thread_id": thread["id"]})
            yield f"data: {data}\n\n"
    except Exception as e:
        yield f"data: {json.dumps({'error': str(e)})}\n\n"
        return

    # Save full assistant message
    _save_message(thread["id"], user_id, "assistant", "".join(full_response))

    # Update thread title from first message if still default
    if thread.get("title") == "New Chat":
        title = message[:60]
        supabase.table("threads").update({"title": title}).eq("id", thread["id"]).execute()

    yield f"data: {json.dumps({'done': True, 'thread_id': thread['id']})}\n\n"


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
    # Verify ownership via RLS (service role bypasses, so we check explicitly)
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
