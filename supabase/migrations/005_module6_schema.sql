-- Module 6: Hybrid Search & Reranking

-- GIN index on chunks.content for full-text search
CREATE INDEX idx_chunks_fts ON public.chunks USING GIN (to_tsvector('english', content));

-- keyword_search_chunks: full-text search over chunks
-- Returns chunk_id for RRF deduplication in the Python layer
CREATE OR REPLACE FUNCTION keyword_search_chunks(
  search_query           text,
  match_user_id          uuid,
  match_count            int   DEFAULT 10,
  match_metadata_filter  jsonb DEFAULT NULL
)
RETURNS TABLE (chunk_id uuid, content text, document_name text, rank real)
LANGUAGE plpgsql AS $$
BEGIN
  RETURN QUERY
  SELECT
    c.id                                                                          AS chunk_id,
    c.content,
    d.name                                                                        AS document_name,
    ts_rank(to_tsvector('english', c.content), plainto_tsquery('english', search_query)) AS rank
  FROM public.chunks c
  JOIN public.documents d ON d.id = c.document_id
  WHERE c.user_id = match_user_id
    AND to_tsvector('english', c.content) @@ plainto_tsquery('english', search_query)
    AND (match_metadata_filter IS NULL OR d.metadata @> match_metadata_filter)
  ORDER BY rank DESC
  LIMIT match_count;
END;
$$;

-- Update match_chunks to also return chunk_id for RRF deduplication.
-- Replaces the 5-param version added in Module 4.
DROP FUNCTION IF EXISTS public.match_chunks(vector, uuid, integer, double precision, jsonb);

CREATE OR REPLACE FUNCTION match_chunks(
  query_embedding        vector(1536),
  match_user_id          uuid,
  match_count            int   DEFAULT 5,
  match_threshold        float DEFAULT 0.7,
  match_metadata_filter  jsonb DEFAULT NULL
)
RETURNS TABLE (chunk_id uuid, content text, document_name text, similarity float)
LANGUAGE plpgsql AS $$
BEGIN
  RETURN QUERY
  SELECT
    c.id                                          AS chunk_id,
    c.content,
    d.name                                        AS document_name,
    1 - (c.embedding <=> query_embedding)         AS similarity
  FROM public.chunks c
  JOIN public.documents d ON d.id = c.document_id
  WHERE c.user_id = match_user_id
    AND 1 - (c.embedding <=> query_embedding) > match_threshold
    AND (match_metadata_filter IS NULL OR d.metadata @> match_metadata_filter)
  ORDER BY c.embedding <=> query_embedding
  LIMIT match_count;
END;
$$;
