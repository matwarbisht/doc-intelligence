-- Phase 5 semantic enrichment and 768-dimensional Gemini vector index.

create index chunk_embeddings_gemini_768_cosine_idx
on public.chunk_embeddings
using hnsw ((embedding::extensions.vector(768)) extensions.vector_cosine_ops)
where provider = 'gemini' and dimension = 768;

create index entity_mentions_entity_id_idx
on public.entity_mentions (entity_id);

create index relationships_run_idx
on public.relationships (extraction_run_id);
