from services.embedding_service import embed_text


def _vector_search(
    query: str,
    user_id: str,
    supabase_client,
    count: int = 10,
    threshold: float = 0.1,
    metadata_filter: dict | None = None,
) -> list[dict]:
    """Run vector similarity search and return candidate chunks."""
    embedding = embed_text(query)
    rpc_params = {
        "query_embedding": embedding,
        "match_user_id": user_id,
        "match_count": count,
        "match_threshold": threshold,
    }
    if metadata_filter:
        rpc_params["match_metadata_filter"] = metadata_filter

    result = supabase_client.rpc("match_chunks", rpc_params).execute()
    return [
        {
            "chunk_id": row["chunk_id"],
            "content": row["content"],
            "document_name": row["document_name"],
            "score": row["similarity"],
        }
        for row in (result.data or [])
    ]


def _keyword_search(
    query: str,
    user_id: str,
    supabase_client,
    count: int = 10,
    metadata_filter: dict | None = None,
) -> list[dict]:
    """Run full-text keyword search and return candidate chunks."""
    rpc_params = {
        "search_query": query,
        "match_user_id": user_id,
        "match_count": count,
    }
    if metadata_filter:
        rpc_params["match_metadata_filter"] = metadata_filter

    result = supabase_client.rpc("keyword_search_chunks", rpc_params).execute()
    return [
        {
            "chunk_id": row["chunk_id"],
            "content": row["content"],
            "document_name": row["document_name"],
            "score": row["rank"],
        }
        for row in (result.data or [])
    ]


def _reciprocal_rank_fusion(
    vector_results: list[dict],
    keyword_results: list[dict],
    k: int = 60,
) -> list[dict]:
    """
    Combine two ranked lists using Reciprocal Rank Fusion.

    RRF score = sum(1 / (k + position)) across all lists a chunk appears in.
    Position is 1-indexed. Deduplicates by chunk_id.
    """
    scores: dict[str, float] = {}
    chunks: dict[str, dict] = {}

    for position, chunk in enumerate(vector_results, start=1):
        cid = chunk["chunk_id"]
        scores[cid] = scores.get(cid, 0.0) + 1.0 / (k + position)
        chunks[cid] = chunk

    for position, chunk in enumerate(keyword_results, start=1):
        cid = chunk["chunk_id"]
        scores[cid] = scores.get(cid, 0.0) + 1.0 / (k + position)
        chunks[cid] = chunk

    ranked = sorted(scores.keys(), key=lambda cid: scores[cid], reverse=True)
    return [
        {**chunks[cid], "rrf_score": scores[cid]}
        for cid in ranked
    ]


def hybrid_search(
    query: str,
    user_id: str,
    supabase_client,
    candidate_count: int = 10,
    metadata_filter: dict | None = None,
) -> list[dict]:
    """
    Run hybrid search (vector + keyword) combined via RRF.

    Returns up to `candidate_count` chunks with keys:
      chunk_id, content, document_name, rrf_score
    """
    vector_results = _vector_search(
        query, user_id, supabase_client,
        count=candidate_count,
        threshold=0.1,
        metadata_filter=metadata_filter,
    )
    keyword_results = _keyword_search(
        query, user_id, supabase_client,
        count=candidate_count,
        metadata_filter=metadata_filter,
    )

    fused = _reciprocal_rank_fusion(vector_results, keyword_results)
    return fused[:candidate_count]
