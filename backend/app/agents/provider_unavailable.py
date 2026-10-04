from typing import Any

from app.agents.base import BaseAgent


class ProviderUnavailableAgent(BaseAgent):
    provider_label = "external provider"
    unavailable_status = "not_configured"

    async def execute(self, input_data: dict[str, Any]) -> dict[str, Any]:
        return {
            "agent": self.definition.id,
            "status": self.unavailable_status,
            "data_status": "NOT_CONFIGURED",
            "result": None,
            "missing_information": [],
            "warnings": [f"{self.provider_label} is not configured; no live result was generated."],
            "sources": [],
        }