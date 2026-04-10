from openai import OpenAI
from config import settings
from langsmith import traceable
from typing import Iterator, Callable
import json

_client = OpenAI(
    base_url=settings.llm_base_url,
    api_key=settings.llm_api_key,
)

RETRIEVE_TOOL = {
    "type": "function",
    "function": {
        "name": "retrieve_chunks",
        "description": (
            "Search the user's document knowledge base for relevant information. "
            "Call this when answering questions that may be answered by uploaded documents. "
            "Use metadata_filter to restrict results to specific document types, topics, "
            "languages, or authors when the user's query implies a specific subset of documents."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "The search query to find relevant document chunks",
                },
                "metadata_filter": {
                    "type": "object",
                    "description": (
                        "Optional JSONB filter to restrict retrieval to documents matching "
                        "specific metadata. Supported keys: document_type (string), "
                        "language (string), author (string). "
                        "Only include when the user explicitly targets a document subset."
                    ),
                    "additionalProperties": True,
                },
            },
            "required": ["query"],
        },
    },
}


@traceable(name="chat_completions_stream", run_type="llm")
def stream_chat_response(
    messages: list[dict],
    retrieval_fn: Callable[[str, dict | None], str],
    user_id: str,
) -> Iterator[str]:
    """
    Stream a chat response using Chat Completions API.
    Handles one round of tool calling (retrieve_chunks) then streams final response.
    retrieval_fn: callable that takes query str and returns context str
    """
    # Pass 1: may trigger tool call
    stream = _client.chat.completions.create(
        model=settings.llm_model,
        messages=messages,
        tools=[RETRIEVE_TOOL],
        tool_choice="auto",
        stream=True,
    )

    tool_call_id = None
    tool_call_name = None
    tool_args_chunks: list[str] = []

    for chunk in stream:
        delta = chunk.choices[0].delta if chunk.choices else None
        if delta is None:
            continue

        # Accumulate tool call
        if delta.tool_calls:
            tc = delta.tool_calls[0]
            if tc.id:
                tool_call_id = tc.id
            if tc.function and tc.function.name:
                tool_call_name = tc.function.name
            if tc.function and tc.function.arguments:
                tool_args_chunks.append(tc.function.arguments)
        elif delta.content:
            yield delta.content

    # If a tool was called, execute it and do Pass 2
    if tool_call_id and tool_call_name == "retrieve_chunks":
        args = json.loads("".join(tool_args_chunks))
        query = args.get("query", "")
        metadata_filter = args.get("metadata_filter", None)
        context = retrieval_fn(query, metadata_filter)

        # Append assistant tool-call message + tool result to history
        messages = messages + [
            {
                "role": "assistant",
                "tool_calls": [{
                    "id": tool_call_id,
                    "type": "function",
                    "function": {
                        "name": "retrieve_chunks",
                        "arguments": "".join(tool_args_chunks),
                    },
                }],
            },
            {
                "role": "tool",
                "tool_call_id": tool_call_id,
                "content": context,
            },
        ]

        # Pass 2: stream final answer (no tools)
        stream2 = _client.chat.completions.create(
            model=settings.llm_model,
            messages=messages,
            stream=True,
        )
        for chunk in stream2:
            delta = chunk.choices[0].delta if chunk.choices else None
            if delta and delta.content:
                yield delta.content
