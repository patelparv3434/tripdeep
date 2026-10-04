from abc import ABC, abstractmethod
from typing import Any

from app.schemas.agents import AgentDefinition


class BaseAgent(ABC):
    definition: AgentDefinition

    async def validate_input(self, input_data: dict[str, Any]) -> dict[str, Any]:
        return input_data

    @abstractmethod
    async def execute(self, input_data: dict[str, Any]) -> dict[str, Any]:
        raise NotImplementedError

    async def validate_output(self, output_data: dict[str, Any]) -> dict[str, Any]:
        return output_data

    async def handle_error(self, error: Exception) -> dict[str, Any]:
        return {
            "status": "failed",
            "error": {"type": type(error).__name__, "message": str(error)},
        }