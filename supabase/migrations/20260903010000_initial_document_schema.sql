-- Stage 1 document intelligence schema.
-- Derived data is always linked to a document version and source evidence.

create schema if not exists extensions;
create extension if not exists vector with schema extensions;

create or replace function public.set_updated_at()
returns trigger
language plpgsql
set search_path = ''
as $$
begin
  new.updated_at = now();
  return new;
end;
$$;

create table public.documents (
  id uuid primary key default gen_random_uuid(),
  filename text not null,
  mime_type text not null,
  storage_path text not null,
  content_hash text not null unique,
  status text not null default 'uploaded'
    check (status in (
      'uploaded',
      'queued',
      'parsing',
      'extracting',
      'embedding',
      'indexing',
      'ready',
      'parsing_failed',
      'extraction_failed',
      'embedding_failed',
      'indexing_failed'
    )),
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create trigger documents_set_updated_at
before update on public.documents
for each row execute function public.set_updated_at();

create table public.document_versions (
  id uuid primary key default gen_random_uuid(),
  document_id uuid not null references public.documents(id) on delete cascade,
  version integer not null check (version > 0),
  parser_provider text,
  parser_version text,
  created_at timestamptz not null default now(),
  unique (document_id, version)
);

create index document_versions_document_id_idx
on public.document_versions (document_id);

create table public.processing_jobs (
  id uuid primary key default gen_random_uuid(),
  document_version_id uuid not null references public.document_versions(id) on delete cascade,
  stage text not null
    check (stage in ('queued', 'parsing', 'extracting', 'embedding', 'indexing')),
  status text not null default 'pending'
    check (status in ('pending', 'running', 'succeeded', 'failed')),
  progress double precision not null default 0 check (progress between 0 and 1),
  attempts integer not null default 0 check (attempts >= 0),
  error text,
  started_at timestamptz,
  completed_at timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index processing_jobs_version_status_idx
on public.processing_jobs (document_version_id, status);

create trigger processing_jobs_set_updated_at
before update on public.processing_jobs
for each row execute function public.set_updated_at();

create table public.document_elements (
  id uuid primary key default gen_random_uuid(),
  document_version_id uuid not null references public.document_versions(id) on delete cascade,
  parent_element_id uuid references public.document_elements(id) on delete set null,
  ordinal integer not null check (ordinal >= 0),
  element_type text not null
    check (element_type in (
      'title',
      'heading',
      'paragraph',
      'narrative_text',
      'list',
      'list_item',
      'table',
      'image',
      'caption',
      'footer',
      'header',
      'unknown'
    )),
  text_content text,
  page_number integer check (page_number is null or page_number > 0),
  structured_content jsonb,
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  unique (document_version_id, ordinal)
);

create index document_elements_version_page_idx
on public.document_elements (document_version_id, page_number, ordinal);

create table public.chunks (
  id uuid primary key default gen_random_uuid(),
  document_version_id uuid not null references public.document_versions(id) on delete cascade,
  ordinal integer not null check (ordinal >= 0),
  content text not null check (length(content) > 0),
  section text,
  page_start integer check (page_start is null or page_start > 0),
  page_end integer check (page_end is null or page_end > 0),
  source_element_ids uuid[] not null default '{}'::uuid[],
  content_hash text not null,
  metadata jsonb not null default '{}'::jsonb,
  search_vector tsvector generated always as (
    to_tsvector('simple', coalesce(section, '') || ' ' || content)
  ) stored,
  created_at timestamptz not null default now(),
  check (page_start is null or page_end is null or page_end >= page_start),
  unique (document_version_id, ordinal),
  unique (document_version_id, content_hash)
);

create index chunks_version_idx on public.chunks (document_version_id);
create index chunks_search_vector_idx on public.chunks using gin (search_vector);

create table public.chunk_embeddings (
  id uuid primary key default gen_random_uuid(),
  chunk_id uuid not null references public.chunks(id) on delete cascade,
  provider text not null,
  model_name text not null,
  model_version text,
  dimension integer not null check (dimension > 0),
  embedding extensions.vector not null,
  created_at timestamptz not null default now(),
  check (extensions.vector_dims(embedding) = dimension),
  unique (chunk_id, provider, model_name, dimension)
);

create index chunk_embeddings_chunk_id_idx on public.chunk_embeddings (chunk_id);

comment on column public.chunk_embeddings.embedding is
  'Dimensionless during the MVP so providers/models remain replaceable. Filter by dimension before distance operations.';

create table public.extraction_runs (
  id uuid primary key default gen_random_uuid(),
  document_version_id uuid not null references public.document_versions(id) on delete cascade,
  provider text not null,
  model_name text not null,
  model_version text,
  prompt_version text not null,
  schema_version text not null,
  status text not null default 'pending'
    check (status in ('pending', 'running', 'succeeded', 'failed')),
  document_type text,
  summary text,
  topics text[] not null default '{}'::text[],
  error text,
  created_at timestamptz not null default now(),
  completed_at timestamptz
);

create index extraction_runs_version_idx
on public.extraction_runs (document_version_id, created_at desc);

create table public.entities (
  id uuid primary key default gen_random_uuid(),
  extraction_run_id uuid not null references public.extraction_runs(id) on delete cascade,
  canonical_name text not null,
  entity_type text not null
    check (entity_type in (
      'person',
      'organization',
      'location',
      'product',
      'date',
      'money',
      'percentage',
      'metric',
      'event',
      'unknown'
    )),
  normalized_value text,
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);

create index entities_run_type_idx on public.entities (extraction_run_id, entity_type);
create index entities_canonical_name_idx on public.entities (lower(canonical_name));

create table public.entity_mentions (
  id uuid primary key default gen_random_uuid(),
  entity_id uuid not null references public.entities(id) on delete cascade,
  chunk_id uuid not null references public.chunks(id) on delete cascade,
  surface_text text not null,
  confidence double precision check (confidence is null or confidence between 0 and 1),
  start_offset integer check (start_offset is null or start_offset >= 0),
  end_offset integer check (end_offset is null or end_offset >= 0),
  created_at timestamptz not null default now(),
  check (start_offset is null or end_offset is null or end_offset >= start_offset),
  unique (entity_id, chunk_id, surface_text, start_offset)
);

create index entity_mentions_chunk_id_idx on public.entity_mentions (chunk_id);

create table public.facts (
  id uuid primary key default gen_random_uuid(),
  extraction_run_id uuid not null references public.extraction_runs(id) on delete cascade,
  source_chunk_id uuid not null references public.chunks(id) on delete cascade,
  subject text not null,
  predicate text not null,
  object_value text not null,
  qualifiers jsonb not null default '{}'::jsonb,
  confidence double precision check (confidence is null or confidence between 0 and 1),
  created_at timestamptz not null default now()
);

create index facts_run_idx on public.facts (extraction_run_id);
create index facts_source_chunk_idx on public.facts (source_chunk_id);
create index facts_subject_predicate_idx on public.facts (lower(subject), predicate);

create table public.relationships (
  id uuid primary key default gen_random_uuid(),
  extraction_run_id uuid not null references public.extraction_runs(id) on delete cascade,
  source_chunk_id uuid not null references public.chunks(id) on delete cascade,
  subject_entity_id uuid not null references public.entities(id) on delete cascade,
  predicate text not null,
  object_entity_id uuid references public.entities(id) on delete cascade,
  object_text text,
  qualifiers jsonb not null default '{}'::jsonb,
  confidence double precision check (confidence is null or confidence between 0 and 1),
  created_at timestamptz not null default now(),
  check (num_nonnulls(object_entity_id, object_text) = 1)
);

create index relationships_subject_idx on public.relationships (subject_entity_id, predicate);
create index relationships_object_entity_idx
on public.relationships (object_entity_id)
where object_entity_id is not null;

create table public.queries (
  id uuid primary key default gen_random_uuid(),
  query_text text not null,
  query_type text not null check (query_type in ('keyword', 'semantic', 'structured', 'hybrid')),
  response jsonb,
  created_at timestamptz not null default now()
);

comment on table public.documents is 'Stable identity and original-file metadata.';
comment on table public.document_versions is 'Immutable processing versions for a document.';
comment on table public.document_elements is 'Application-owned canonical document structure.';
comment on table public.chunks is 'Retrieval units with element and page provenance.';
comment on table public.facts is 'Flexible subject-predicate-object facts linked to source chunks.';

-- The browser does not access Postgres directly in Stage 1. Enabling RLS without
-- client policies keeps the public schema closed while the backend service role
-- retains access.
alter table public.documents enable row level security;
alter table public.document_versions enable row level security;
alter table public.processing_jobs enable row level security;
alter table public.document_elements enable row level security;
alter table public.chunks enable row level security;
alter table public.chunk_embeddings enable row level security;
alter table public.extraction_runs enable row level security;
alter table public.entities enable row level security;
alter table public.entity_mentions enable row level security;
alter table public.facts enable row level security;
alter table public.relationships enable row level security;
alter table public.queries enable row level security;
