-- Fix: ts_rank() returns real, not double precision (float)
-- Recreate keyword_search_chunks with the correct return type.
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
