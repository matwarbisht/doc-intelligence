-- Durable, concurrency-safe counters and sanitized operational events.

create table public.quota_counters (
  subject_type text not null check (subject_type in ('user', 'ip', 'document', 'global')),
  subject_key text not null,
  metric text not null,
  window_start timestamptz not null,
  window_seconds integer not null check (window_seconds > 0),
  used bigint not null default 0 check (used >= 0),
  updated_at timestamptz not null default now(),
  primary key (subject_type, subject_key, metric, window_start, window_seconds)
);

create index quota_counters_cleanup_idx
on public.quota_counters (window_start, window_seconds);

create table public.quota_alerts (
  subject_type text not null,
  subject_key text not null,
  metric text not null,
  window_start timestamptz not null,
  window_seconds integer not null,
  threshold smallint not null check (threshold in (70, 90, 100)),
  created_at timestamptz not null default now(),
  primary key (
    subject_type, subject_key, metric, window_start, window_seconds, threshold
  )
);

create table public.usage_events (
  id uuid primary key default gen_random_uuid(),
  user_id uuid references auth.users(id) on delete set null,
  ip_hash text,
  action text not null,
  outcome text not null check (outcome in ('allowed', 'rejected', 'released')),
  code text,
  amount bigint not null default 1 check (amount >= 0),
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);

create index usage_events_created_at_idx on public.usage_events (created_at desc);
create index usage_events_user_created_at_idx
on public.usage_events (user_id, created_at desc)
where user_id is not null;

alter table public.quota_counters enable row level security;
alter table public.quota_alerts enable row level security;
alter table public.usage_events enable row level security;

comment on table public.quota_counters is
  'Atomic fixed-window application quotas. subject_key never contains a raw IP address.';
comment on table public.usage_events is
  'Sanitized safeguard outcomes without document content, filenames, emails, or credentials.';
