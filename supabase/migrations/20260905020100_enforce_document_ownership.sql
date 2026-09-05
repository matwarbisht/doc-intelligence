-- Contract ownership after the explicit legacy-data backfill has completed.

do $$
begin
  if exists (select 1 from public.documents where owner_id is null) then
    raise exception using
      message = 'documents.owner_id still contains null values',
      hint = 'Run the legacy ownership dry-run and apply commands before retrying this migration.';
  end if;

  if exists (select 1 from public.queries where user_id is null) then
    raise exception using
      message = 'queries.user_id still contains null values',
      hint = 'Run the legacy ownership dry-run and apply commands before retrying this migration.';
  end if;

  if exists (
    select 1
    from public.queries q
    join public.documents d on d.id = q.document_id
    where q.document_id is not null and q.user_id <> d.owner_id
  ) then
    raise exception using
      message = 'a document-scoped query belongs to a different user than its document',
      hint = 'Resolve the conflicting ownership before retrying this migration.';
  end if;
end;
$$;

alter table public.documents
alter column owner_id set not null;

alter table public.queries
alter column user_id set not null;

alter table public.documents
add constraint documents_id_owner_id_key unique (id, owner_id);

alter table public.queries
drop constraint queries_document_id_fkey;

alter table public.queries
add constraint queries_document_owner_fkey
foreign key (document_id, user_id)
references public.documents (id, owner_id)
on delete set null (document_id);

comment on constraint queries_document_owner_fkey on public.queries is
  'A document-scoped query must belong to the same user as its document.';
