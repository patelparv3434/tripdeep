from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


FieldType = Literal["text", "textarea", "number", "date", "select", "multiselect", "checkbox", "file", "object", "array"]


class InputField(BaseModel):
    name: str
    label: str
    type: FieldType
    required: bool = False
    options: list[str] = Field(default_factory=list)
    description: str | None = None
    default: Any = None
    minimum: float | None = None
    maximum: float | None = None


class InputSchema(BaseModel):
    fields: list[InputField]


class AgentDefinition(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: str
    name: str
    description: str
    input_schema: InputSchema
    supported_outputs: list[str]
    dependencies: list[str] = Field(default_factory=list)
    provider_requirements: list[str] = Field(default_factory=list)
    status: Literal["available", "partially_available", "not_configured"]


class AgentCatalog(BaseModel):
    agents: list[AgentDefinition]
    total: int