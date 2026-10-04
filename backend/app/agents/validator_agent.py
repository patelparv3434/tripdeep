from typing import Any

from app.agents.base import BaseAgent
from app.agents.registry import AGENTS_BY_ID
from app.schemas.validation import ValidationRequest
from app.validators.travel import validate_travel_data


class ValidatorAgent(BaseAgent):
    definition = AGENTS_BY_ID["validator"]

    async def validate_input(self, input_data: dict[str, Any]) -> dict[str, Any]:
        ValidationRequest.model_validate(input_data)
        return input_data

    async def execute(self, input_data: dict[str, Any]) -> dict[str, Any]:
        request = ValidationRequest.model_validate(input_data)
        return validate_travel_data(request).model_dump(mode="json")

    async def validate_output(self, output_data: dict[str, Any]) -> dict[str, Any]:
        from app.schemas.validation import ValidationResponse

        return ValidationResponse.model_validate(output_data).model_dump(mode="json")