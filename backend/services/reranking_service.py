from pydantic import BaseModel
from config import settings
from services.llm_service import _client

_CHUNK_PREVIEW_CHARS = 500


class ChunkScore(BaseModel):
    index: int    # 0-based index in the input list
    score: float  # 0.0–1.0 relevance to query


class RerankResponse(BaseModel):
    scores: list[ChunkScore]


def rerank_chunks(query: str, chunks: list[dict], top_k: int = 5) -> list[dict]:
    """
    Rerank candidate chunks by relevance to the query using the LLM.

    If len(chunks) <= top_k, returns chunks as-is without an LLM call.
    On any error, falls back to returning chunks[:top_k] unmodified.
    """
    if len(chunks) <= top_k:
        return chunks

    numbered = "\n\n".join(
        f"[{i}] {chunk['content'][:_CHUNK_PREVIEW_CHARS]}"
        for i, chunk in enumerate(chunks)
    )

    system_prompt = (
        "You are a relevance scoring assistant. "
        "Given a user query and a numbered list of text chunks, "
        "score each chunk's relevance to the query on a scale of 0.0 (irrelevant) to 1.0 (highly relevant). "
        "Return a JSON object with a single key 'scores' containing an array of objects, "
        "each with 'index' (the chunk number) and 'score' (the relevance score). "
        "Include a score for every chunk."
    )
    user_message = f"Query: {query}\n\nChunks:\n{numbered}"

    try:
        response = _client.chat.completions.create(
            model=settings.llm_model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message},
            ],
            response_format={"type": "json_object"},
            stream=False,
        )
        raw = response.choices[0].message.content or "{}"
        rerank_result = RerankResponse.model_validate_json(raw)

        score_map = {cs.index: cs.score for cs in rerank_result.scores}
        scored_chunks = [
            (score_map.get(i, 0.0), chunk)
            for i, chunk in enumerate(chunks)
        ]
        scored_chunks.sort(key=lambda x: x[0], reverse=True)
        return [chunk for _, chunk in scored_chunks[:top_k]]

    except Exception:
        # Reranking is non-critical — fall back to unmodified order
        return chunks[:top_k]
