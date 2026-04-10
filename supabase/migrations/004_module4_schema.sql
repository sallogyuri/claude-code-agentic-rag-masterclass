-- Module 4: Metadata Extraction
ALTER TABLE public.documents ADD COLUMN metadata JSONB;

-- GIN index for fast JSONB containment queries (@>)
CREATE INDEX idx_documents_metadata ON public.documents USING GIN (metadata);

-- Drop old 4-param overload so the new 5-param version (with DEFAULT NULL) is unambiguous
DROP FUNCTION IF EXISTS public.match_chunks(vector, uuid, integer, double precision);

-- Replace match_chunks() — adds optional metadata filter, backward compatible (defaults NULL)
CREATE OR REPLACE FUNCTION match_chunks(
  query_embedding        vector(1536),
  match_user_id          uuid,
  match_count            int   DEFAULT 5,
  match_threshold        float DEFAULT 0.7,
  match_metadata_filter  jsonb DEFAULT NULL
)
RETURNS TABLE (content text, document_name text, similarity float)
LANGUAGE plpgsql AS $$
BEGIN
  RETURN QUERY
  SELECT
    c.content,
    d.name AS document_name,
    1 - (c.embedding <=> query_embedding) AS similarity
  FROM public.chunks c
  JOIN public.documents d ON d.id = c.document_id
  WHERE c.user_id = match_user_id
    AND 1 - (c.embedding <=> query_embedding) > match_threshold
    AND (match_metadata_filter IS NULL OR d.metadata @> match_metadata_filter)
  ORDER BY c.embedding <=> query_embedding
  LIMIT match_count;
END;
$$;
