alter table public.queries
add column document_id uuid references public.documents (id) on delete set null;

create index queries_document_id_created_at_idx
on public.queries (document_id, created_at desc)
where document_id is not null;

comment on column public.queries.document_id is
  'Optional document scope applied to every retrieval strategy for this query.';
