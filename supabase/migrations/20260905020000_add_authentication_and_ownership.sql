-- Add application profiles and user ownership without deleting pre-authentication data.

create table public.profiles (
  user_id uuid primary key references auth.users(id) on delete cascade,
  status text not null default 'active'
    check (status in ('active', 'suspended')),
  display_name text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create trigger profiles_set_updated_at
before update on public.profiles
for each row execute function public.set_updated_at();

create or replace function public.create_profile_for_auth_user()
returns trigger
language plpgsql
security definer
set search_path = ''
as $$
begin
  insert into public.profiles (user_id)
  values (new.id)
  on conflict (user_id) do nothing;
  return new;
end;
$$;

create trigger auth_user_created_create_profile
after insert on auth.users
for each row execute function public.create_profile_for_auth_user();

alter table public.documents
add column owner_id uuid references auth.users(id) on delete restrict;

alter table public.queries
add column user_id uuid references auth.users(id) on delete restrict;

alter table public.documents
drop constraint documents_content_hash_key;

create unique index documents_owner_content_hash_key
on public.documents (owner_id, content_hash)
where owner_id is not null;

create index documents_owner_created_at_idx
on public.documents (owner_id, created_at desc, id desc);

create index queries_user_created_at_idx
on public.queries (user_id, created_at desc, id desc);

alter table public.profiles enable row level security;

revoke all on table public.profiles from anon;
revoke all on table public.profiles from authenticated;
grant select on table public.profiles to authenticated;

create policy profiles_select_own
on public.profiles
for select
to authenticated
using ((select auth.uid()) is not null and (select auth.uid()) = user_id);

comment on table public.profiles is
  'Application profile and suspension state for a Supabase Auth identity.';

comment on column public.documents.owner_id is
  'Owner of the document aggregate. Derived records inherit ownership through the document.';

comment on column public.queries.user_id is
  'Authenticated user whose private corpus was queried.';
