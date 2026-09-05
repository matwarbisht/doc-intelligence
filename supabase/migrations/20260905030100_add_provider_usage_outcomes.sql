-- Extend sanitized safeguard telemetry for provider-attempt results.

alter table public.usage_events
drop constraint usage_events_outcome_check;

alter table public.usage_events
add constraint usage_events_outcome_check
check (outcome in ('allowed', 'rejected', 'released', 'succeeded', 'failed'));
