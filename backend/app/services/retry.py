import asyncio
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import TypeVar

T = TypeVar("T")


class TransientProviderError(Exception):
    """A provider or database error that may succeed on a bounded retry."""


class CircuitOpenError(Exception):
    """Raised when calls are paused after repeated provider failures."""


async def retry_transient(
    operation: Callable[[], Awaitable[T]],
    *,
    max_attempts: int = 3,
    base_delay: float = 0.25,
    max_delay: float = 4.0,
    sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
) -> tuple[T, int]:
    if max_attempts < 1:
        raise ValueError("max_attempts must be at least one")

    for attempt in range(1, max_attempts + 1):
        try:
            return await operation(), attempt - 1
        except TransientProviderError:
            if attempt == max_attempts:
                raise
            await sleep(min(base_delay * (2 ** (attempt - 1)), max_delay))
    raise RuntimeError("Retry loop exited unexpectedly")


@dataclass
class CircuitBreaker:
    failure_threshold: int = 3
    reset_timeout: float = 30.0
    failures: int = 0
    opened_at: float | None = None

    @property
    def is_open(self) -> bool:
        if self.opened_at is None:
            return False
        if time.monotonic() - self.opened_at >= self.reset_timeout:
            self.opened_at = None
            self.failures = 0
            return False
        return True

    async def call(self, operation: Callable[[], Awaitable[T]]) -> T:
        if self.is_open:
            raise CircuitOpenError("Provider circuit is open; retry after the reset interval")
        try:
            result = await operation()
        except TransientProviderError:
            self.failures += 1
            if self.failures >= self.failure_threshold:
                self.opened_at = time.monotonic()
            raise
        self.failures = 0
        self.opened_at = None
        return result