from pathlib import Path

MIGRATIONS = Path(__file__).parents[3] / "supabase" / "migrations"
SCHEMA = MIGRATIONS / "20260903010000_initial_document_schema.sql"
STORAGE = MIGRATIONS / "20260903010100_create_documents_bucket.sql"
PROCESSING = MIGRATIONS / "20260904010000_processing_pipeline_constraints.sql"
SEED = MIGRATIONS.parent / "seed.sql"


def test_initial_schema_contains_stage_one_records() -> None:
    sql = SCHEMA.read_text()

    expected_tables = {
        "documents",
        "document_versions",
        "processing_jobs",
        "document_elements",
        "chunks",
        "chunk_embeddings",
        "extraction_runs",
        "entities",
        "entity_mentions",
        "facts",
        "relationships",
        "queries",
    }

    for table in expected_tables:
        assert f"create table public.{table}" in sql
        assert f"alter table public.{table} enable row level security" in sql

    assert "create extension if not exists vector" in sql
    assert "source_element_ids uuid[]" in sql
    assert "source_chunk_id uuid" in sql
    assert "using gin (search_vector)" in sql


def test_documents_bucket_is_private_and_constrained() -> None:
    sql = STORAGE.read_text()

    assert "'documents'" in sql
    assert "values (\n  'documents',\n  'documents',\n  false," in sql
    assert "application/pdf" in sql
    assert "52428800" in sql


def test_local_seed_is_synthetic_and_has_provenance() -> None:
    sql = SEED.read_text()

    assert "Synthetic local development document" in sql
    assert "insert into public.document_elements" in sql
    assert "insert into public.chunks" in sql
    assert "source_element_ids" in sql
    assert "insert into public.facts" in sql


def test_processing_migration_supports_idempotent_stages_and_repeated_content() -> None:
    sql = PROCESSING.read_text()

    assert "unique (document_version_id, stage)" in sql
    assert "drop constraint chunks_document_version_id_content_hash_key" in sql
