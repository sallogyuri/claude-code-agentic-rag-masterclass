-- Enable UUID generation
create extension if not exists "pgcrypto";

-- Threads table: each user owns their threads
create table public.threads (
  id          uuid primary key default gen_random_uuid(),
  user_id     uuid not null references auth.users(id) on delete cascade,
  title       text not null default 'New Chat',
  -- The Responses API thread ID - used to continue conversations
  openai_thread_id text,
  created_at  timestamptz not null default now(),
  updated_at  timestamptz not null default now()
);

alter table public.threads enable row level security;

create policy "threads: users see own rows"
  on public.threads for all
  using (auth.uid() = user_id)
  with check (auth.uid() = user_id);

-- Messages table: human + assistant messages per thread
create table public.messages (
  id          uuid primary key default gen_random_uuid(),
  thread_id   uuid not null references public.threads(id) on delete cascade,
  user_id     uuid not null references auth.users(id) on delete cascade,
  role        text not null check (role in ('user', 'assistant')),
  content     text not null,
  created_at  timestamptz not null default now()
);

alter table public.messages enable row level security;

create policy "messages: users see own rows"
  on public.messages for all
  using (auth.uid() = user_id)
  with check (auth.uid() = user_id);

-- Auto-update threads.updated_at
create or replace function public.set_updated_at()
returns trigger language plpgsql as $$
begin
  new.updated_at = now();
  return new;
end;
$$;

create trigger threads_updated_at
  before update on public.threads
  for each row execute procedure public.set_updated_at();
