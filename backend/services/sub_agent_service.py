from langsmith import traceable
from typing import Iterator, Callable
import json

from services.llm_service import RETRIEVE_TOOL, _client
from config import settings

MAX_SUB_AGENT_ITERATIONS = 5


@traceable(name="sub_agent_stream", run_type="llm")
def run_sub_agent_stream(
    task: str,
    document_name: str,
    user_id: str,
    retrieval_fn: Callable[[str, dict | None], str],
) -> Iterator[dict]:
    """
    Isolated sub-agent that analyses a single document.
    Only has access to retrieve_chunks (no spawn_sub_agent — prevents recursion).
    Yields typed event dicts: sub_agent_delta, sub_agent_tool_call.
    """
    system_prompt = (
        f"You are a document analyst for '{document_name}'. "
        f"Task: {task}. "
        "Use retrieve_chunks multiple times if needed to fully address the task."
    )
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": task},
    ]

    try:
        for _iteration in range(MAX_SUB_AGENT_ITERATIONS):
            stream = _client.chat.completions.create(
                model=settings.llm_model,
                messages=messages,
                tools=[RETRIEVE_TOOL],
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
                    yield {"type": "sub_agent_delta", "delta": delta.content}

            if finish_reason == "stop" or not tool_calls_by_index:
                break

            # Build assistant tool-calls message
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

            # Execute tool calls
            for idx in sorted(tool_calls_by_index.keys()):
                tc = tool_calls_by_index[idx]
                args_str = "".join(tc["args_chunks"])
                try:
                    args = json.loads(args_str)
                except json.JSONDecodeError:
                    args = {}

                query = args.get("query", "")
                metadata_filter = args.get("metadata_filter", None)

                yield {"type": "sub_agent_tool_call", "tool": "retrieve_chunks", "query": query}
                context = retrieval_fn(query, metadata_filter)
                messages = messages + [{
                    "role": "tool",
                    "tool_call_id": tc["id"],
                    "content": context,
                }]

    except Exception as e:
        yield {"type": "sub_agent_delta", "delta": f"\n[Sub-agent error: {str(e)}]"}
        return
