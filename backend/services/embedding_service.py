from openai import OpenAI
from config import settings

_client = OpenAI(api_key=settings.openai_api_key)  # direct OpenAI for embeddings


def embed_text(text: str) -> list[float]:
    response = _client.embeddings.create(
        model="text-embedding-3-small",
        input=text,
    )
    return response.data[0].embedding
