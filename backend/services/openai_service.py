from openai import OpenAI
from config import settings
from typing import Iterator

client = OpenAI(api_key=settings.openai_api_key)


def get_or_create_thread(openai_thread_id: str | None) -> str:
    """Return existing thread ID or create a new one."""
    if openai_thread_id:
        return openai_thread_id
    thread = client.beta.threads.create()
    return thread.id
