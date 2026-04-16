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

SPAWN_SUB_AGENT_TOOL = {
    "type": "function",
    "function": {
        "name": "spawn_sub_agent",
        "description": (
            "Delegate comprehensive full-document analysis to an isolated sub-agent. "
            "Use when the user's query requires thorough analysis of an entire specific document "
            "(e.g. 'summarize the whole report', 'what are all the recommendations in X'). "
            "Do NOT use for targeted lookups — use retrieve_chunks for those. "
            "The sub-agent has its own retrieval loop scoped to the named document."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "task": {"type": "string", "description": "The analysis task for the sub-agent"},
                "document_name": {"type": "string", "description": "Exact document name to scope retrieval to"},
            },
            "required": ["task", "document_name"],
        },
    },
}

TEXT_TO_SQL_TOOL = {
    "type": "function",
    "function": {
        "name": "text_to_sql",
        "description": (
            "Convert a natural language question into a SQL query and execute it against structured/tabular data. "
            "ALWAYS use this tool — without trying retrieve_chunks first — for ANY of these: "
            "sales analytics (e.g. 'total revenue by region', 'top salesperson', 'orders in January', 'best-selling product'), "
            "document statistics (e.g. 'how many documents', 'which files are pending', 'count by status'), "
            "thread or message history (e.g. 'how many threads', 'recent conversations'). "
            "Do NOT use for document text content — use retrieve_chunks for that."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Natural language question about the structured data",
                }
            },
            "required": ["query"],
        },
    },
}

WEB_SEARCH_TOOL = {
    "type": "function",
    "function": {
        "name": "web_search",
        "description": (
            "Search the web for current or general information not found in uploaded documents. "
            "Use as a fallback when retrieve_chunks returns no relevant results, or when the "
            "question clearly requires up-to-date external information. "
            "Always cite the source URLs from results in your response."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Web search query",
                }
            },
            "required": ["query"],
        },
    },
}

MAX_ITERATIONS = 10


@traceable(name="chat_completions_stream", run_type="llm")
def stream_chat_response(
    messages: list[dict],
    retrieval_fn: Callable[[str, dict | None], str],
    sub_agent_fn: Callable[[str, str], Iterator[dict]],
    text_to_sql_fn: Callable[[str], str],
    web_search_fn: Callable[[str], str],
    user_id: str,
) -> Iterator[dict]:
    """
    Agentic loop over Chat Completions API.
    Supports retrieve_chunks (inline tool) and spawn_sub_agent (delegates to sub-agent).
    Yields typed event dicts: delta, tool_call_start, tool_call_end,
    sub_agent_start, sub_agent_end (sub_agent_delta/tool_call events come from sub_agent_fn).
    """
    iteration = 0
    while iteration < MAX_ITERATIONS:
        stream = _client.chat.completions.create(
            model=settings.llm_model,
            messages=messages,
            tools=[RETRIEVE_TOOL, SPAWN_SUB_AGENT_TOOL, TEXT_TO_SQL_TOOL, WEB_SEARCH_TOOL],
            tool_choice="auto",
            stream=True,
        )

        tool_calls_by_index: dict[int, dict] = {}
        finish_reason = None

        for chunk in stream:
            if not chunk.choices:
                continue
            choice = chunk.choices[0]
            if choice.finish_reason is not None:
                finish_reason = choice.finish_reason
            delta = choice.delta
            if delta is None:
                continue
            if delta.tool_calls:
                for tc in delta.tool_calls:
                    idx = getattr(tc, "index", 0) or 0
                    if idx not in tool_calls_by_index:
                        tool_calls_by_index[idx] = {"id": None, "name": None, "args_chunks": []}
                    if tc.id:
                        tool_calls_by_index[idx]["id"] = tc.id
                    if tc.function and tc.function.name:
                        tool_calls_by_index[idx]["name"] = tc.function.name
                    if tc.function and tc.function.arguments:
                        tool_calls_by_index[idx]["args_chunks"].append(tc.function.arguments)
            elif delta.content:
                yield {"type": "delta", "delta": delta.content}

        if finish_reason == "stop" or not tool_calls_by_index:
            break

        # Build assistant message with all tool calls for this turn
        tool_calls_list = []
        for idx in sorted(tool_calls_by_index.keys()):
            tc = tool_calls_by_index[idx]
            tool_calls_list.append({
                "id": tc["id"],
                "type": "function",
                "function": {
                    "name": tc["name"],
                    "arguments": "".join(tc["args_chunks"]),
                },
            })
        messages = messages + [{"role": "assistant", "tool_calls": tool_calls_list}]

        # Execute each tool call in index order
        for idx in sorted(tool_calls_by_index.keys()):
            tc = tool_calls_by_index[idx]
            args_str = "".join(tc["args_chunks"])
            try:
                args = json.loads(args_str)
            except json.JSONDecodeError:
                args = {}

            tool_name = tc["name"]

            if tool_name == "retrieve_chunks":
                query = args.get("query", "")
                metadata_filter = args.get("metadata_filter", None)
                yield {"type": "tool_call_start", "tool": "retrieve_chunks", "args": {"query": query, "metadata_filter": metadata_filter}}
                context = retrieval_fn(query, metadata_filter)
                yield {"type": "tool_call_end", "tool": "retrieve_chunks"}
                messages = messages + [{
                    "role": "tool",
                    "tool_call_id": tc["id"],
                    "content": context,
                }]

            elif tool_name == "spawn_sub_agent":
                task = args.get("task", "")
                document_name = args.get("document_name", "")
                yield {"type": "sub_agent_start", "task": task, "document": document_name}
                yield from sub_agent_fn(task, document_name)
                yield {"type": "sub_agent_end"}
                messages = messages + [{
                    "role": "tool",
                    "tool_call_id": tc["id"],
                    "content": f"Sub-agent completed analysis of '{document_name}' for task: {task}",
                }]

            elif tool_name == "text_to_sql":
                query = args.get("query", "")
                yield {"type": "tool_call_start", "tool": "text_to_sql", "args": {"query": query}}
                sql, result = text_to_sql_fn(query)
                yield {"type": "tool_call_end", "tool": "text_to_sql", "sql": sql}
                messages = messages + [{
                    "role": "tool",
                    "tool_call_id": tc["id"],
                    "content": result,
                }]

            elif tool_name == "web_search":
                query = args.get("query", "")
                yield {"type": "tool_call_start", "tool": "web_search", "args": {"query": query}}
                result = web_search_fn(query)
                yield {"type": "tool_call_end", "tool": "web_search"}
                messages = messages + [{
                    "role": "tool",
                    "tool_call_id": tc["id"],
                    "content": result,
                }]

        iteration += 1
