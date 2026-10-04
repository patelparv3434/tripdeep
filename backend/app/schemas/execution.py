from typing import Any

from pydantic import BaseModel, Field


class AgentExecutionRequest(BaseModel):
    input_data: dict[str, Any] = Field(default_factory=dict)
    trip_id: str | None = None


class AgentExecutionResponse(BaseModel):
    execution_id: str
    request_id: str
    agent_id: str
    status: str
    validation_status: str | None = None
    output: dict[str, Any] | None = None
    validation: dict[str, Any] | None = None
    reproduction_case_id: str | None = None
    error: str | None = None