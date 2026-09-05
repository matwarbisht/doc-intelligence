"""Feature controls, durable quotas, provider circuits, and sanitized telemetry."""

import hashlib
import hmac
import logging
from asyncio import Lock
from collections import deque
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from time import monotonic
from typing import Protocol
from uuid import UUID

from app.repositories import (
    QuotaLimit,
    QuotaRejectedError,
    QuotaReservation,
    QuotaUsage,
    SafeguardRepository,
)

logger = logging.getLogger(__name__)
HOUR_SECONDS = 60 * 60
DAY_SECONDS = 24 * HOUR_SECONDS


@dataclass(frozen=True, slots=True)
class Capabilities:
    public_signup: bool
    uploads: bool
    processing: bool
    processing_retries: bool
    ask: bool


@dataclass(frozen=True, slots=True)
class SafeguardLimits:
    user_uploads_per_hour: int = 10
    user_documents_per_day: int = 25
    user_upload_bytes_per_day: int = 262_144_000
    user_asks_per_hour: int = 30
    user_asks_per_day: int = 100
    user_retries_per_hour: int = 5
    user_retries_per_day: int = 10
    user_max_documents: int = 100
    retry_cooldown_seconds: int = 300
    ip_uploads_per_hour: int = 30
    ip_asks_per_hour: int = 120
    global_documents_per_day: int = 250
    global_upload_bytes_per_day: int = 2_621_440_000
    global_asks_per_day: int = 500
    user_unstructured_attempts_per_day: int = 30
    global_unstructured_attempts_per_day: int = 250
    user_gemini_extractions_per_day: int = 30
    global_gemini_extractions_per_day: int = 250
    user_gemini_embedding_calls_per_day: int = 1_000
    global_gemini_embedding_calls_per_day: int = 10_000
    user_gemini_query_embeddings_per_day: int = 100
    global_gemini_query_embeddings_per_day: int = 500
    user_gemini_answers_per_day: int = 100
    global_gemini_answers_per_day: int = 500
    provider_circuit_failure_threshold: int = 5
    provider_circuit_window_seconds: int = 60
    provider_circuit_cooldown_seconds: int = 60


@dataclass(frozen=True, slots=True)
class _ProviderPolicy:
    user_limit: int
    global_limit: int
    code: str
    detail: str


@dataclass(slots=True)
class _CircuitState:
    failures: deque[float] = field(default_factory=lambda: deque[float]())
    open_until: float = 0


class SafeguardViolation(RuntimeError):
    def __init__(
        self,
        *,
        status_code: int,
        code: str,
        detail: str,
        retry_after_seconds: int | None = None,
    ) -> None:
        super().__init__(detail)
        self.status_code = status_code
        self.code = code
        self.detail = detail
        self.retry_after_seconds = retry_after_seconds


class AlertSink(Protocol):
    async def emit(self, usage: QuotaUsage, threshold: int) -> None: ...


class LogAlertSink:
    async def emit(self, usage: QuotaUsage, threshold: int) -> None:
        item = usage.limit
        logger.warning(
            "Safeguard threshold reached",
            extra={
                "event": "safeguard.threshold.reached",
                "subject_type": item.subject_type,
                "subject_key": item.subject_key,
                "metric": item.metric,
                "threshold": threshold,
                "used": usage.used,
                "limit": item.limit,
                "code": item.code,
            },
        )


class SafeguardService:
    def __init__(
        self,
        repository: SafeguardRepository,
        *,
        capabilities: Capabilities,
        limits: SafeguardLimits,
        ip_hash_salt: str,
        alert_sink: AlertSink | None = None,
    ) -> None:
        self._repository = repository
        self.capabilities = capabilities
        self._limits = limits
        self._ip_hash_salt = ip_hash_salt.encode()
        self._alert_sink = alert_sink
        self._circuits: dict[tuple[str, str], _CircuitState] = {}
        self._circuit_lock = Lock()

    async def guard_upload_request(self, user_id: UUID, source_ip: str | None) -> None:
        self._require(self.capabilities.uploads, "uploads_disabled", "Uploads are unavailable.")
        ip_hash = self.hash_ip(source_ip)
        await self._reserve(
            "upload_request",
            user_id,
            ip_hash,
            (
                self._hourly(
                    "user",
                    str(user_id),
                    "upload_requests",
                    1,
                    self._limits.user_uploads_per_hour,
                    "upload_hourly_limit",
                    "Hourly upload limit reached.",
                ),
                self._hourly(
                    "ip",
                    ip_hash,
                    "upload_requests",
                    1,
                    self._limits.ip_uploads_per_hour,
                    "ip_upload_hourly_limit",
                    "Too many upload requests from this network.",
                ),
            ),
        )

    async def reserve_upload(
        self, user_id: UUID, source_ip: str | None, size_bytes: int
    ) -> QuotaReservation:
        ip_hash = self.hash_ip(source_ip)
        limits = (
            self._daily(
                "user",
                str(user_id),
                "documents",
                1,
                self._limits.user_documents_per_day,
                "daily_document_limit",
                "Daily document limit reached.",
            ),
            self._daily(
                "user",
                str(user_id),
                "upload_bytes",
                size_bytes,
                self._limits.user_upload_bytes_per_day,
                "daily_upload_byte_limit",
                "Daily upload byte limit reached.",
            ),
            self._daily(
                "global",
                "all",
                "documents",
                1,
                self._limits.global_documents_per_day,
                "global_document_budget",
                "Document intake is temporarily unavailable.",
                service_unavailable=True,
            ),
            self._daily(
                "global",
                "all",
                "upload_bytes",
                size_bytes,
                self._limits.global_upload_bytes_per_day,
                "global_upload_byte_budget",
                "Document intake is temporarily unavailable.",
                service_unavailable=True,
            ),
        )
        return await self._reserve(
            "upload_acceptance",
            user_id,
            ip_hash,
            limits,
            document_owner_id=user_id,
            max_documents=self._limits.user_max_documents,
        )

    async def release_upload(
        self,
        user_id: UUID,
        source_ip: str | None,
        reservation: QuotaReservation,
    ) -> None:
        await self._repository.release(reservation)
        await self._record(user_id, self.hash_ip(source_ip), "upload_acceptance", "released")

    async def guard_ask(self, user_id: UUID, source_ip: str | None) -> None:
        self._require(self.capabilities.ask, "ask_disabled", "Questions are unavailable.")
        ip_hash = self.hash_ip(source_ip)
        await self._reserve(
            "ask",
            user_id,
            ip_hash,
            (
                self._hourly(
                    "user",
                    str(user_id),
                    "asks",
                    1,
                    self._limits.user_asks_per_hour,
                    "ask_hourly_limit",
                    "Hourly question limit reached.",
                ),
                self._daily(
                    "user",
                    str(user_id),
                    "asks",
                    1,
                    self._limits.user_asks_per_day,
                    "daily_question_limit",
                    "Daily question limit reached.",
                ),
                self._hourly(
                    "ip",
                    ip_hash,
                    "asks",
                    1,
                    self._limits.ip_asks_per_hour,
                    "ip_ask_hourly_limit",
                    "Too many questions from this network.",
                ),
                self._daily(
                    "global",
                    "all",
                    "asks",
                    1,
                    self._limits.global_asks_per_day,
                    "global_question_budget",
                    "Question answering is temporarily unavailable.",
                    service_unavailable=True,
                ),
            ),
        )

    async def guard_retry(self, user_id: UUID, source_ip: str | None, document_id: UUID) -> None:
        self._require(
            self.capabilities.processing,
            "processing_disabled",
            "Document processing is unavailable.",
        )
        self._require(
            self.capabilities.processing_retries,
            "processing_retries_disabled",
            "Processing retries are unavailable.",
        )
        ip_hash = self.hash_ip(source_ip)
        await self._reserve(
            "processing_retry",
            user_id,
            ip_hash,
            (
                self._hourly(
                    "user",
                    str(user_id),
                    "retries",
                    1,
                    self._limits.user_retries_per_hour,
                    "retry_hourly_limit",
                    "Hourly retry limit reached.",
                ),
                self._daily(
                    "user",
                    str(user_id),
                    "retries",
                    1,
                    self._limits.user_retries_per_day,
                    "daily_retry_limit",
                    "Daily retry limit reached.",
                ),
                self._fixed(
                    "document",
                    str(document_id),
                    "retry",
                    1,
                    1,
                    self._limits.retry_cooldown_seconds,
                    "retry_cooldown",
                    "Wait before retrying this document again.",
                ),
            ),
        )

    def processing_enabled(self) -> bool:
        return self.capabilities.processing

    async def before_provider_attempt(
        self,
        *,
        user_id: UUID,
        provider: str,
        operation: str,
    ) -> None:
        policy = self._provider_policy(provider, operation)
        await self._require_closed_circuit(provider, operation)
        await self._reserve(
            f"provider.{provider}.{operation}",
            user_id,
            None,
            (
                self._daily(
                    "user",
                    str(user_id),
                    f"provider.{provider}.{operation}.attempts",
                    1,
                    policy.user_limit,
                    f"user_{policy.code}",
                    policy.detail,
                ),
                self._daily(
                    "global",
                    "all",
                    f"provider.{provider}.{operation}.attempts",
                    1,
                    policy.global_limit,
                    policy.code,
                    policy.detail,
                    service_unavailable=True,
                ),
            ),
        )

    async def after_provider_attempt(
        self,
        *,
        user_id: UUID,
        provider: str,
        operation: str,
        status_code: int | None,
        succeeded: bool,
    ) -> None:
        code = None if succeeded else self._provider_failure_code(status_code)
        await self._record(
            user_id,
            None,
            f"provider.{provider}.{operation}.result",
            "succeeded" if succeeded else "failed",
            code,
        )
        await self._update_circuit(
            provider,
            operation,
            transient_failure=(
                not succeeded and (status_code is None or status_code == 429 or status_code >= 500)
            ),
            succeeded=succeeded,
        )

    def hash_ip(self, source_ip: str | None) -> str:
        normalized = (source_ip or "unknown").strip().lower()
        return hmac.new(self._ip_hash_salt, normalized.encode(), hashlib.sha256).hexdigest()

    async def _reserve(
        self,
        action: str,
        user_id: UUID,
        ip_hash: str | None,
        limits: tuple[QuotaLimit, ...],
        *,
        document_owner_id: UUID | None = None,
        max_documents: int | None = None,
    ) -> QuotaReservation:
        try:
            reservation = await self._repository.reserve(
                limits,
                document_owner_id=document_owner_id,
                max_documents=max_documents,
            )
        except QuotaRejectedError as error:
            item = error.limit
            await self._record(user_id, ip_hash, action, "rejected", item.code)
            retry_after = self._retry_after(item)
            raise SafeguardViolation(
                status_code=503 if item.service_unavailable else 429,
                code=item.code,
                detail=item.detail,
                retry_after_seconds=retry_after,
            ) from error
        await self._record(user_id, ip_hash, action, "allowed")
        await self._emit_thresholds(reservation)
        return reservation

    async def _emit_thresholds(self, reservation: QuotaReservation) -> None:
        if self._alert_sink is None:
            return
        for usage in reservation.usages:
            percentage = usage.used * 100 / usage.limit.limit
            for threshold in (70, 90, 100):
                if percentage < threshold:
                    continue
                try:
                    if await self._repository.register_alert(usage, threshold):
                        await self._alert_sink.emit(usage, threshold)
                except Exception:
                    logger.exception(
                        "Failed to deliver safeguard threshold alert",
                        extra={
                            "event": "safeguard.alert.delivery_failed",
                            "subject_type": usage.limit.subject_type,
                            "subject_key": usage.limit.subject_key,
                            "metric": usage.limit.metric,
                            "threshold": threshold,
                        },
                    )

    async def _record(
        self,
        user_id: UUID,
        ip_hash: str | None,
        action: str,
        outcome: str,
        code: str | None = None,
    ) -> None:
        try:
            await self._repository.record_event(
                user_id=user_id,
                ip_hash=ip_hash,
                action=action,
                outcome=outcome,
                code=code,
            )
        except Exception:
            logger.exception("Failed to record sanitized safeguard event")

    @staticmethod
    def _require(enabled: bool, code: str, detail: str) -> None:
        if not enabled:
            raise SafeguardViolation(status_code=503, code=code, detail=detail)

    @staticmethod
    def _window_start(window_seconds: int) -> datetime:
        now = datetime.now(UTC)
        epoch = int(now.timestamp())
        return datetime.fromtimestamp(epoch - epoch % window_seconds, UTC)

    def _hourly(
        self,
        subject_type: str,
        subject_key: str,
        metric: str,
        amount: int,
        limit: int,
        code: str,
        detail: str,
    ) -> QuotaLimit:
        return self._fixed(
            subject_type, subject_key, metric, amount, limit, HOUR_SECONDS, code, detail
        )

    def _daily(
        self,
        subject_type: str,
        subject_key: str,
        metric: str,
        amount: int,
        limit: int,
        code: str,
        detail: str,
        *,
        service_unavailable: bool = False,
    ) -> QuotaLimit:
        return self._fixed(
            subject_type,
            subject_key,
            metric,
            amount,
            limit,
            DAY_SECONDS,
            code,
            detail,
            service_unavailable=service_unavailable,
        )

    def _fixed(
        self,
        subject_type: str,
        subject_key: str,
        metric: str,
        amount: int,
        limit: int,
        window_seconds: int,
        code: str,
        detail: str,
        *,
        service_unavailable: bool = False,
    ) -> QuotaLimit:
        return QuotaLimit(
            subject_type=subject_type,
            subject_key=subject_key,
            metric=metric,
            window_start=self._window_start(window_seconds),
            window_seconds=window_seconds,
            amount=amount,
            limit=limit,
            code=code,
            detail=detail,
            service_unavailable=service_unavailable,
        )

    def _provider_policy(self, provider: str, operation: str) -> _ProviderPolicy:
        policies = {
            ("unstructured", "job_submission"): _ProviderPolicy(
                self._limits.user_unstructured_attempts_per_day,
                self._limits.global_unstructured_attempts_per_day,
                "unstructured_budget_exhausted",
                "Document parsing is temporarily unavailable.",
            ),
            ("gemini", "extraction"): _ProviderPolicy(
                self._limits.user_gemini_extractions_per_day,
                self._limits.global_gemini_extractions_per_day,
                "gemini_extraction_budget_exhausted",
                "Document extraction is temporarily unavailable.",
            ),
            ("gemini", "document_embedding"): _ProviderPolicy(
                self._limits.user_gemini_embedding_calls_per_day,
                self._limits.global_gemini_embedding_calls_per_day,
                "gemini_embedding_budget_exhausted",
                "Document embedding is temporarily unavailable.",
            ),
            ("gemini", "query_embedding"): _ProviderPolicy(
                self._limits.user_gemini_query_embeddings_per_day,
                self._limits.global_gemini_query_embeddings_per_day,
                "gemini_query_embedding_budget_exhausted",
                "Question answering is temporarily unavailable.",
            ),
            ("gemini", "answer_generation"): _ProviderPolicy(
                self._limits.user_gemini_answers_per_day,
                self._limits.global_gemini_answers_per_day,
                "gemini_answer_budget_exhausted",
                "Question answering is temporarily unavailable.",
            ),
        }
        try:
            return policies[(provider, operation)]
        except KeyError as error:
            raise ValueError(
                f"Unsupported metered provider operation: {provider}.{operation}"
            ) from error

    async def _require_closed_circuit(self, provider: str, operation: str) -> None:
        async with self._circuit_lock:
            state = self._circuits.get((provider, operation))
            remaining = 0 if state is None else state.open_until - monotonic()
        if remaining > 0:
            raise SafeguardViolation(
                status_code=503,
                code=f"{provider}_{operation}_circuit_open",
                detail="The external processing service is temporarily unavailable.",
                retry_after_seconds=max(1, int(remaining) + 1),
            )

    async def _update_circuit(
        self,
        provider: str,
        operation: str,
        *,
        transient_failure: bool,
        succeeded: bool,
    ) -> None:
        now = monotonic()
        async with self._circuit_lock:
            state = self._circuits.setdefault((provider, operation), _CircuitState())
            if succeeded:
                state.failures.clear()
                return
            if not transient_failure:
                return
            cutoff = now - self._limits.provider_circuit_window_seconds
            while state.failures and state.failures[0] < cutoff:
                state.failures.popleft()
            state.failures.append(now)
            if len(state.failures) >= self._limits.provider_circuit_failure_threshold:
                state.open_until = now + self._limits.provider_circuit_cooldown_seconds
                state.failures.clear()

    @staticmethod
    def _provider_failure_code(status_code: int | None) -> str:
        return "network_error" if status_code is None else f"http_{status_code}"

    @staticmethod
    def _retry_after(item: QuotaLimit) -> int:
        end = item.window_start + timedelta(seconds=item.window_seconds)
        return max(1, int((end - datetime.now(UTC)).total_seconds()) + 1)
