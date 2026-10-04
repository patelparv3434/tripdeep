import asyncio

import pytest

from app.services.retry import CircuitBreaker, CircuitOpenError, TransientProviderError, retry_transient


def test_retry_uses_bounded_exponential_backoff() -> None:
    attempts = 0
    delays: list[float] = []

    async def operation() -> str:
        nonlocal attempts
        attempts += 1
        if attempts < 3:
            raise TransientProviderError("temporary timeout")
        return "ok"

    async def record_sleep(delay: float) -> None:
        delays.append(delay)

    result, retries = asyncio.run(
        retry_transient(operation, max_attempts=3, base_delay=0.1, sleep=record_sleep)
    )

    assert (result, retries, attempts) == ("ok", 2, 3)
    assert delays == [0.1, 0.2]


def test_non_transient_errors_are_not_retried() -> None:
    attempts = 0

    async def operation() -> None:
        nonlocal attempts
        attempts += 1
        raise ValueError("invalid request")

    with pytest.raises(ValueError):
        asyncio.run(retry_transient(operation, max_attempts=3))
    assert attempts == 1


def test_circuit_breaker_opens_after_threshold() -> None:
    breaker = CircuitBreaker(failure_threshold=2)

    async def fail() -> None:
        raise TransientProviderError("offline")

    with pytest.raises(TransientProviderError):
        asyncio.run(breaker.call(fail))
    with pytest.raises(TransientProviderError):
        asyncio.run(breaker.call(fail))
    with pytest.raises(CircuitOpenError):
        asyncio.run(breaker.call(fail))