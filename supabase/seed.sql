-- Deterministic, synthetic records for local UI and persistence development.
-- Schema belongs in migrations; this file contains data only.

-- Placeholder identity for deterministic data ownership. It intentionally has no password;
-- create a login-capable account through local Supabase Auth when testing sign-in.
insert into auth.users (id, email, raw_user_meta_data, raw_app_meta_data)
values (
  '00000000-0000-4000-8000-000000000001',
  'seed-user@example.test',
  '{}'::jsonb,
  '{}'::jsonb
)
on conflict (id) do nothing;

insert into public.documents (
  id,
  filename,
  mime_type,
  storage_path,
  content_hash,
  owner_id,
  status,
  metadata
)
values (
  '10000000-0000-4000-8000-000000000001',
  'acme-quarterly-update.txt',
  'text/plain',
  'seed/acme-quarterly-update.txt',
  'seed:acme-quarterly-update-v1',
  '00000000-0000-4000-8000-000000000001',
  'ready',
  '{"seeded": true, "description": "Synthetic local development document"}'::jsonb
)
on conflict (id) do nothing;

insert into public.document_versions (
  id,
  document_id,
  version,
  parser_provider,
  parser_version
)
values (
  '20000000-0000-4000-8000-000000000001',
  '10000000-0000-4000-8000-000000000001',
  1,
  'seed',
  '1'
)
on conflict (id) do nothing;

insert into public.document_elements (
  id,
  document_version_id,
  ordinal,
  element_type,
  text_content,
  page_number
)
values
  (
    '30000000-0000-4000-8000-000000000001',
    '20000000-0000-4000-8000-000000000001',
    0,
    'heading',
    'Quarterly update',
    1
  ),
  (
    '30000000-0000-4000-8000-000000000002',
    '20000000-0000-4000-8000-000000000001',
    1,
    'narrative_text',
    'Acme Corp expanded operations into India during Q3.',
    1
  ),
  (
    '30000000-0000-4000-8000-000000000003',
    '20000000-0000-4000-8000-000000000001',
    2,
    'narrative_text',
    'Revenue increased 24 percent year over year to 4.2 billion dollars.',
    1
  )
on conflict (id) do nothing;

insert into public.chunks (
  id,
  document_version_id,
  ordinal,
  content,
  section,
  page_start,
  page_end,
  source_element_ids,
  content_hash,
  metadata
)
values (
  '40000000-0000-4000-8000-000000000001',
  '20000000-0000-4000-8000-000000000001',
  0,
  'Acme Corp expanded operations into India during Q3. Revenue increased 24 percent year over year to 4.2 billion dollars.',
  'Quarterly update',
  1,
  1,
  array[
    '30000000-0000-4000-8000-000000000002'::uuid,
    '30000000-0000-4000-8000-000000000003'::uuid
  ],
  'seed:acme-quarterly-update:chunk:0',
  '{"seeded": true}'::jsonb
)
on conflict (id) do nothing;

insert into public.extraction_runs (
  id,
  document_version_id,
  provider,
  model_name,
  prompt_version,
  schema_version,
  status,
  document_type,
  summary,
  topics,
  completed_at
)
values (
  '50000000-0000-4000-8000-000000000001',
  '20000000-0000-4000-8000-000000000001',
  'seed',
  'seed-model',
  '1',
  '1',
  'succeeded',
  'quarterly report',
  'Acme expanded into India and reported year-over-year revenue growth.',
  array['expansion', 'revenue'],
  now()
)
on conflict (id) do nothing;

insert into public.entities (
  id,
  extraction_run_id,
  canonical_name,
  entity_type,
  metadata
)
values
  (
    '60000000-0000-4000-8000-000000000001',
    '50000000-0000-4000-8000-000000000001',
    'Acme Corp',
    'organization',
    '{"seeded": true}'::jsonb
  ),
  (
    '60000000-0000-4000-8000-000000000002',
    '50000000-0000-4000-8000-000000000001',
    'India',
    'location',
    '{"seeded": true}'::jsonb
  )
on conflict (id) do nothing;

insert into public.facts (
  id,
  extraction_run_id,
  source_chunk_id,
  subject,
  predicate,
  object_value,
  confidence
)
values (
  '70000000-0000-4000-8000-000000000001',
  '50000000-0000-4000-8000-000000000001',
  '40000000-0000-4000-8000-000000000001',
  'Acme Corp revenue',
  'year_over_year_growth',
  '24 percent',
  1
)
on conflict (id) do nothing;
