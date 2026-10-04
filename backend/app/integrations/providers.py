from typing import Any, Protocol


class LLMProvider(Protocol):
    async def generate(self, prompt: str, context: dict[str, Any]) -> str: ...


class WeatherProvider(Protocol):
    async def forecast(self, destination: str, start_date: str, end_date: str) -> dict[str, Any]: ...


class HotelProvider(Protocol):
    async def search(self, criteria: dict[str, Any]) -> dict[str, Any]: ...


class TransportationProvider(Protocol):
    async def search(self, criteria: dict[str, Any]) -> dict[str, Any]: ...


class TourGuideProvider(Protocol):
    async def search(self, criteria: dict[str, Any]) -> dict[str, Any]: ...


class InsuranceKnowledgeProvider(Protocol):
    async def retrieve(self, query: str, context: dict[str, Any]) -> list[dict[str, Any]]: ...


class DocumentExtractor(Protocol):
    async def extract(self, filename: str, media_type: str, content: bytes) -> dict[str, Any]: ...


class ProviderUnavailableError(Exception):
    """Raised when an optional provider has no authorized configured adapter."""