from datetime import date
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class ValidationStatus(StrEnum):
    PASS = "PASS"
    FAIL = "FAIL"
    WARNING = "WARNING"
    MISSING = "MISSING"
    NEEDS_REVIEW = "NEEDS_REVIEW"
    NOT_APPLICABLE = "NOT_APPLICABLE"


class ValidationCheck(BaseModel):
    field: str
    status: ValidationStatus
    message: str
    evidence: list[str] = Field(default_factory=list)


class ValidationRequest(BaseModel):
    data: dict[str, Any]
    agent_outputs: dict[str, dict[str, Any]] = Field(default_factory=dict)
    required_fields: list[str] = Field(default_factory=list)
    applicable_rules: list[str] = Field(default_factory=list)
    as_of: date | None = None


class ValidationResponse(BaseModel):
    status: ValidationStatus
    checks: list[ValidationCheck]
    missing_information: list[str]
    has_conflicts: bool