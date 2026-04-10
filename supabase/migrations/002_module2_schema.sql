-- Enable pgvector
create extension if not exists vector;

-- Drop openai_thread_id column (no longer needed)
alter table public.threads drop column if exists openai_thread_id;

-- Documents table
create table public.documents (
  id           uuid primary key default gen_random_uuid(),
  user_id      uuid not null references auth.users(id) on delete cascade,
  name         text not null,
  size         bigint not null,
  mime_type    text not null,
  storage_path text not null,
  status       text not null default 'pending' check (status in ('pending','processing','complete','error')),
  created_at   timestamptz not null default now()
);
alter table public.documents enable row level security;
create policy "documents: users see own rows"
  on public.documents for all
  using (auth.uid() = user_id) with check (auth.uid() = user_id);

-- Chunks table (pgvector)
create table public.chunks (
  id           uuid primary key default gen_random_uuid(),
  document_id  uuid not null references public.documents(id) on delete cascade,
  user_id      uuid not null references auth.users(id) on delete cascade,
  content      text not null,
  chunk_index  int not null,
  embedding    vector(1536),
  created_at   timestamptz not null default now()
);
alter table public.chunks enable row level security;
create policy "chunks: users see own rows"
  on public.chunks for all
  using (auth.uid() = user_id) with check (auth.uid() = user_id);
create index on public.chunks using ivfflat (embedding vector_cosine_ops) with (lists = 100);

-- Ingestion jobs table (for Realtime status)
create table public.ingestion_jobs (
  id            uuid primary key default gen_random_uuid(),
  document_id   uuid not null references public.documents(id) on delete cascade,
  user_id       uuid not null references auth.users(id) on delete cascade,
  status        text not null default 'pending' check (status in ('pending','processing','complete','error')),
  error_message text,
  created_at    timestamptz not null default now(),
  updated_at    timestamptz not null default now()
);
alter table public.ingestion_jobs enable row level security;
create policy "ingestion_jobs: users see own rows"
  on public.ingestion_jobs for all
  using (auth.uid() = user_id) with check (auth.uid() = user_id);

create trigger ingestion_jobs_updated_at
  before update on public.ingestion_jobs
  for each row execute procedure public.set_updated_at();

-- pgvector similarity search function
create or replace function match_chunks(
  query_embedding vector(1536),
  match_user_id   uuid,
  match_count     int default 5,
  match_threshold float default 0.7
)
returns table (content text, document_name text, similarity float)
language plpgsql as $$
begin
  return query
  select
    c.content,
    d.name as document_name,
    1 - (c.embedding <=> query_embedding) as similarity
  from public.chunks c
  join public.documents d on d.id = c.document_id
  where c.user_id = match_user_id
    and 1 - (c.embedding <=> query_embedding) > match_threshold
  order by c.embedding <=> query_embedding
  limit match_count;
end;
$$;
