from langsmith import traceable
from openai import OpenAI
from config import settings
from typing import Iterator

client = OpenAI(api_key=settings.openai_api_key)


@traceable(name="openai_responses_stream", run_type="llm")
def traced_stream_response(
    openai_thread_id: str,
    user_message: str,
    user_id: str,
) -> Iterator[str]:
    """
    Traced wrapper around the Responses API streaming call.
    LangSmith captures inputs/outputs and the run_type for the LLM span.
    """
    client.beta.threads.messages.create(
        thread_id=openai_thread_id,
        role="user",
        content=user_message,
    )

    chunks = []
    with client.beta.threads.runs.stream(
        thread_id=openai_thread_id,
        assistant_id=settings.openai_assistant_id,
    ) as stream:
        for text in stream.text_deltas:
            chunks.append(text)
            yield text

    # LangSmith traceable captures the final output
    return "".join(chunks)
