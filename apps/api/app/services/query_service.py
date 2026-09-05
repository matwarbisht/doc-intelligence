"""Hybrid corpus retrieval and grounded-answer orchestration."""

import asyncio
import logging
from datetime import UTC, datetime
from uuid import UUID, uuid4

from app.domain import GeneratedCitation, QueryResult, QueryType, RetrievalHit
from app.providers import AnswerGenerator, EmbeddingProvider
from app.repositories import QueryRepository
from app.services.safeguard_service import SafeguardViolation

logger = logging.getLogger(__name__)


class QueryServiceError(RuntimeError):
    """Raised when a corpus query cannot be completed safely."""


class EmptyQueryError(ValueError):
    """Raised when a query contains no meaningful text."""


class CorpusQueryService:
    _RRF_OFFSET = 60
    _WEIGHTS = {
        QueryType.KEYWORD: 0.8,
        QueryType.SEMANTIC: 1.0,
        QueryType.STRUCTURED: 0.9,
    }

    def __init__(
        self,
        repository: QueryRepository,
        embedding_provider: EmbeddingProvider,
        answer_generator: AnswerGenerator,
        *,
        candidate_limit: int = 10,
        max_sources: int = 8,
    ) -> None:
        self._repository = repository
        self._embedding_provider = embedding_provider
        self._answer_generator = answer_generator
        self._candidate_limit = candidate_limit
        self._max_sources = max_sources

    async def query(
        self,
        question: str,
        *,
        user_id: UUID,
        document_id: UUID | None = None,
    ) -> QueryResult:
        normalized = " ".join(question.split())
        if not normalized:
            raise EmptyQueryError("Question must not be empty.")

        try:
            keyword, semantic, structured = await asyncio.gather(
                self._repository.search_keyword(
                    normalized,
                    user_id=user_id,
                    document_id=document_id,
                    limit=self._candidate_limit,
                ),
                self._semantic_search(normalized, user_id=user_id, document_id=document_id),
                self._repository.search_structured(
                    normalized,
                    user_id=user_id,
                    document_id=document_id,
                    limit=self._candidate_limit,
                ),
            )
            evidence = self._fuse(keyword, semantic, structured)[: self._max_sources]
            logger.info(
                "Corpus retrieval completed",
                extra={
                    "event": "query.retrieval.completed",
                    "keyword_hits": len(keyword),
                    "semantic_hits": len(semantic),
                    "structured_hits": len(structured),
                    "fused_hits": len(evidence),
                    "scope_document_id": str(document_id) if document_id else None,
                },
            )
            if evidence:
                generated = await self._answer_generator.generate(
                    normalized,
                    evidence,
                    user_id=user_id,
                )
                cited = self._resolve_citations(generated.citations, evidence)
                answer = generated.answer
            else:
                cited = ()
                answer = "I couldn't find enough evidence in the ready documents to answer that."
        except SafeguardViolation:
            raise
        except Exception as error:
            raise QueryServiceError("The corpus query could not be completed.") from error

        result = QueryResult(
            id=uuid4(),
            user_id=user_id,
            query=normalized,
            query_type=QueryType.HYBRID,
            document_id=document_id,
            answer=answer,
            sources=cited,
            created_at=datetime.now(UTC),
        )
        try:
            await self._repository.save_query(result)
        except Exception as error:
            raise QueryServiceError("The corpus query could not be recorded.") from error
        return result

    async def _semantic_search(
        self, query: str, *, user_id: UUID, document_id: UUID | None
    ) -> tuple[RetrievalHit, ...]:
        vector = await self._embedding_provider.embed_query(query, user_id=user_id)
        return await self._repository.search_semantic(
            vector,
            provider=self._embedding_provider.provider_name,
            model_name=self._embedding_provider.model_name,
            dimension=self._embedding_provider.dimension,
            user_id=user_id,
            document_id=document_id,
            limit=self._candidate_limit,
        )

    def _fuse(
        self,
        *rankings: tuple[RetrievalHit, ...],
    ) -> tuple[RetrievalHit, ...]:
        hits: dict[UUID, RetrievalHit] = {}
        scores: dict[UUID, float] = {}
        match_types: dict[UUID, list[QueryType]] = {}
        for ranking in rankings:
            if not ranking:
                continue
            match_type = ranking[0].match_types[0]
            weight = self._WEIGHTS[match_type]
            for rank, hit in enumerate(ranking, start=1):
                hits.setdefault(hit.chunk_id, hit)
                scores[hit.chunk_id] = scores.get(hit.chunk_id, 0) + weight / (
                    self._RRF_OFFSET + rank
                )
                current_types = match_types.setdefault(hit.chunk_id, [])
                for item in hit.match_types:
                    if item not in current_types:
                        current_types.append(item)

        fused = [
            hit.model_copy(
                update={
                    "score": scores[chunk_id],
                    "match_types": tuple(match_types[chunk_id]),
                }
            )
            for chunk_id, hit in hits.items()
        ]
        return tuple(sorted(fused, key=lambda hit: (-hit.score, str(hit.chunk_id))))

    @staticmethod
    def _resolve_citations(
        citations: tuple[GeneratedCitation, ...], evidence: tuple[RetrievalHit, ...]
    ) -> tuple[RetrievalHit, ...]:
        by_number = {index: hit for index, hit in enumerate(evidence, start=1)}
        resolved: list[RetrievalHit] = []
        seen: set[UUID] = set()
        for citation in citations:
            hit = by_number[citation.source_number]
            if hit.chunk_id != citation.chunk_id:
                raise ValueError("citation does not match the retrieved source")
            if hit.chunk_id not in seen:
                resolved.append(hit.model_copy(update={"citation_number": citation.source_number}))
                seen.add(hit.chunk_id)
        return tuple(resolved)
