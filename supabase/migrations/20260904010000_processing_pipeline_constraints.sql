-- Phase 4 processing idempotency constraints.

alter table public.processing_jobs
add constraint processing_jobs_version_stage_key
unique (document_version_id, stage);

-- Repeated passages are legitimate and must retain their separate provenance.
alter table public.chunks
drop constraint chunks_document_version_id_content_hash_key;
