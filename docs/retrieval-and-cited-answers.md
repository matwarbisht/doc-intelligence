# Retrieval and Cited Answers

Phase 6 turns the ready document corpus into a cross-document question-answering surface. Retrieval remains application-owned and combines three independent signals before any source text is sent to Gemini.

## Query flow

```text
question
   ├── Postgres full-text chunk search
   ├── Gemini RETRIEVAL_QUERY embedding → pgvector cosine search
   └── Postgres fact and entity-mention search
                     ↓
         weighted reciprocal-rank fusion
                     ↓
            bounded evidence set
                     ↓
        Gemini grounded structured answer
                     ↓
       validated citations + source excerpts
```

`POST /api/v1/query` accepts a question of up to 2,000 characters. Only chunks from the latest version of documents whose status is `ready` are eligible for retrieval.

## Hybrid retrieval

The MVP always runs keyword, semantic, and structured retrieval concurrently. It does not spend another model call classifying the question first. Weighted reciprocal-rank fusion combines the ranked lists without pretending the raw Postgres text rank and cosine similarity scores are directly comparable.

The current weights favor semantic retrieval while allowing exact terms and extracted knowledge to raise a chunk's final rank:

- semantic: `1.0`
- structured facts and entity mentions: `0.9`
- keyword: `0.8`

The default candidate pool is 10 results per retriever, and at most 8 fused chunks are sent to answer generation. Both limits are configurable.

## Grounding and citations

Each evidence chunk receives a stable source number before answer generation. Gemini must answer only from those chunks, cite factual claims inline as `[n]`, and return structured citation objects containing the same source number and exact chunk UUID. A system instruction treats retrieved text as untrusted evidence rather than executable instructions and tells the model to ignore commands embedded inside documents.

The adapter rejects source-number/chunk-ID mismatches. The API returns only sources that the answer cited, with filename, page range, excerpt, retrieval score, and contributing retrieval mechanisms. If retrieval finds no evidence, the application returns a deterministic insufficient-evidence response without calling the answer model.

## Persistence and provider boundaries

`QueryRepository` owns keyword, vector, structured retrieval, and query-history persistence. `AnswerGenerator` owns the grounded-answer provider boundary. `EmbeddingProvider.embed_query` distinguishes query embeddings from the `RETRIEVAL_DOCUMENT` embeddings created during ingestion.

Completed queries are written to `public.queries` with the `hybrid` query type, answer, and cited source metadata. Raw provider payloads and credentials are never persisted or returned.

## Configuration

```bash
GEMINI_ANSWER_MODEL=gemini-3.6-flash
RETRIEVAL_CANDIDATE_LIMIT=10
RETRIEVAL_MAX_SOURCES=8
```

The query service also requires `GEMINI_API_KEY`, `GEMINI_EMBEDDING_MODEL`, and `GEMINI_EMBEDDING_DIMENSION`. The answer and extraction models are configured separately so they can be evaluated and upgraded independently later.
