from datetime import date
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator


class TripCreateRequest(BaseModel):
    title: str | None = None
    origin: str = Field(min_length=1, max_length=200)
    destination: str = Field(min_length=1, max_length=200)
    start_date: date
    end_date: date
    adults: int = Field(ge=1)
    children: int = Field(default=0, ge=0)
    child_ages: list[int] = Field(default_factory=list)
    travel_mode: str = "Flight"
    hotel_category: str | None = None
    room_occupancy: int = Field(default=2, ge=1)
    food_preference: str | None = None
    cloud_ai_style_notes: bool = False
    payment_method: str | None = None
    cancellation_required: bool = True
    requirements: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_dates_and_children(self):
        if self.start_date < date.today():
            raise ValueError("Start date cannot be in the past")
        if self.end_date <= self.start_date:
            raise ValueError("End date must be after start date")
        if self.children and self.child_ages and len(self.child_ages) != self.children:
            raise ValueError("If child ages are supplied, provide one age per child")
        return self


class WorkflowAgentInput(BaseModel):
    agent_id: str
    input_data: dict[str, Any] = Field(default_factory=dict)


class TripWorkflowRequest(BaseModel):
    agents: list[WorkflowAgentInput] = Field(min_length=1)


class TripResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    title: str
    origin: str
    destination: str
    start_date: str | None
    end_date: str | None
    status: str
    request_data: dict[str, Any]