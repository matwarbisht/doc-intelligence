from uuid import UUID, uuid4

import pytest

from app.repositories import QuotaUsage
from app.services import (
    Capabilities,
    SafeguardLimits,
    SafeguardService,
    SafeguardViolation,
)
from tests.fakes import InMemorySafeguardRepository

USER_ID = UUID("10000000-0000-4000-8000-000000000001")


def service(
    repository: InMemorySafeguardRepository,
    *,
    capabilities: Capabilities | None = None,
    limits: SafeguardLimits | None = None,
) -> SafeguardService:
    return SafeguardService(
        repository,
        capabilities=capabilities or Capabilities(True, True, True, True, True),
        limits=limits or SafeguardLimits(),
        ip_hash_salt="unit-test-secret-salt",
    )


@pytest.mark.asyncio
async def test_upload_request_limit_is_atomic_and_returns_retry_timing() -> None:
    repository = InMemorySafeguardRepository()
    safeguards = service(
        repository,
        limits=SafeguardLimits(user_uploads_per_hour=1),
    )

    await safeguards.guard_upload_request(USER_ID, "203.0.113.8")
    with pytest.raises(SafeguardViolation) as caught:
        await safeguards.guard_upload_request(USER_ID, "203.0.113.8")

    assert caught.value.status_code == 429
    assert caught.value.code == "upload_hourly_limit"
    assert caught.value.retry_after_seconds is not None
    assert repository.events[-1] == (
        "upload_request",
        "rejected",
        "upload_hourly_limit",
    )


@pytest.mark.asyncio
async def test_global_question_budget_returns_service_unavailable() -> None:
    repository = InMemorySafeguardRepository()
    safeguards = service(
        repository,
        limits=SafeguardLimits(global_asks_per_day=1),
    )

    await safeguards.guard_ask(USER_ID, "203.0.113.8")
    with pytest.raises(SafeguardViolation) as caught:
        await safeguards.guard_ask(uuid4(), "203.0.113.9")

    assert caught.value.status_code == 503
    assert caught.value.code == "global_question_budget"


@pytest.mark.asyncio
async def test_first_reservation_cannot_exceed_its_limit() -> None:
    repository = InMemorySafeguardRepository()
    safeguards = service(
        repository,
        limits=SafeguardLimits(user_upload_bytes_per_day=5),
    )

    with pytest.raises(SafeguardViolation) as caught:
        await safeguards.reserve_upload(USER_ID, "203.0.113.8", 6)

    assert caught.value.code == "daily_upload_byte_limit"
    assert repository.used == {}


@pytest.mark.asyncio
async def test_released_upload_capacity_can_be_reserved_again() -> None:
    repository = InMemorySafeguardRepository()
    safeguards = service(
        repository,
        limits=SafeguardLimits(user_documents_per_day=1, global_documents_per_day=1),
    )

    reservation = await safeguards.reserve_upload(USER_ID, "203.0.113.8", 10)
    await safeguards.release_upload(USER_ID, "203.0.113.8", reservation)
    repeated = await safeguards.reserve_upload(USER_ID, "203.0.113.8", 10)

    assert repeated.usages
    assert ("upload_acceptance", "released", None) in repository.events


@pytest.mark.asyncio
async def test_stored_document_capacity_is_reserved_and_compensated() -> None:
    repository = InMemorySafeguardRepository()
    safeguards = service(repository, limits=SafeguardLimits(user_max_documents=1))

    reservation = await safeguards.reserve_upload(USER_ID, "203.0.113.8", 10)
    with pytest.raises(SafeguardViolation) as caught:
        await safeguards.reserve_upload(USER_ID, "203.0.113.8", 10)

    assert caught.value.code == "stored_document_limit"
    await safeguards.release_upload(USER_ID, "203.0.113.8", reservation)
    assert (await safeguards.reserve_upload(USER_ID, "203.0.113.8", 10)).usages


@pytest.mark.asyncio
async def test_retry_cooldown_is_scoped_to_the_document() -> None:
    repository = InMemorySafeguardRepository()
    safeguards = service(repository)
    document_id = uuid4()

    await safeguards.guard_retry(USER_ID, "203.0.113.8", document_id)
    with pytest.raises(SafeguardViolation) as caught:
        await safeguards.guard_retry(USER_ID, "203.0.113.8", document_id)

    assert caught.value.code == "retry_cooldown"
    await safeguards.guard_retry(USER_ID, "203.0.113.8", uuid4())


@pytest.mark.asyncio
async def test_disabled_feature_fails_before_counter_reservation() -> None:
    repository = InMemorySafeguardRepository()
    safeguards = service(
        repository,
        capabilities=Capabilities(True, False, True, True, True),
    )

    with pytest.raises(SafeguardViolation) as caught:
        await safeguards.guard_upload_request(USER_ID, "203.0.113.8")

    assert caught.value.status_code == 503
    assert caught.value.code == "uploads_disabled"
    assert repository.used == {}


def test_ip_hash_is_stable_without_retaining_the_source_address() -> None:
    safeguards = service(InMemorySafeguardRepository())

    first = safeguards.hash_ip(" 203.0.113.8 ")
    second = safeguards.hash_ip("203.0.113.8")

    assert first == second
    assert "203.0.113.8" not in first
    assert len(first) == 64


@pytest.mark.asyncio
async def test_alert_delivery_failure_does_not_reject_reserved_work() -> None:
    class BrokenAlertSink:
        async def emit(self, usage: QuotaUsage, threshold: int) -> None:
            del usage, threshold
            raise RuntimeError("alert transport unavailable")

    repository = InMemorySafeguardRepository()
    safeguards = SafeguardService(
        repository,
        capabilities=Capabilities(True, True, True, True, True),
        limits=SafeguardLimits(user_uploads_per_hour=1),
        ip_hash_salt="unit-test-secret-salt",
        alert_sink=BrokenAlertSink(),
    )

    await safeguards.guard_upload_request(USER_ID, "203.0.113.8")

    assert repository.events[-1] == ("upload_request", "allowed", None)


@pytest.mark.asyncio
async def test_provider_attempt_budget_is_separate_by_operation() -> None:
    repository = InMemorySafeguardRepository()
    safeguards = service(
        repository,
        limits=SafeguardLimits(global_gemini_answers_per_day=1),
    )

    await safeguards.before_provider_attempt(
        user_id=USER_ID,
        provider="gemini",
        operation="answer_generation",
    )
    with pytest.raises(SafeguardViolation) as caught:
        await safeguards.before_provider_attempt(
            user_id=uuid4(),
            provider="gemini",
            operation="answer_generation",
        )

    assert caught.value.status_code == 503
    assert caught.value.code == "gemini_answer_budget_exhausted"
    await safeguards.before_provider_attempt(
        user_id=USER_ID,
        provider="gemini",
        operation="query_embedding",
    )


@pytest.mark.asyncio
async def test_clustered_transient_failures_open_only_the_affected_circuit() -> None:
    repository = InMemorySafeguardRepository()
    safeguards = service(
        repository,
        limits=SafeguardLimits(
            provider_circuit_failure_threshold=2,
            provider_circuit_cooldown_seconds=60,
        ),
    )
    for _ in range(2):
        await safeguards.after_provider_attempt(
            user_id=USER_ID,
            provider="gemini",
            operation="extraction",
            status_code=429,
            succeeded=False,
        )

    with pytest.raises(SafeguardViolation) as caught:
        await safeguards.before_provider_attempt(
            user_id=USER_ID,
            provider="gemini",
            operation="extraction",
        )

    assert caught.value.code == "gemini_extraction_circuit_open"
    assert caught.value.retry_after_seconds is not None
    await safeguards.before_provider_attempt(
        user_id=USER_ID,
        provider="gemini",
        operation="answer_generation",
    )
