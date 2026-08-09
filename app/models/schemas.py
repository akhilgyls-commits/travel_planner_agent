"""
Pydantic models describing the public API contract.
"""
from datetime import date
from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field, field_validator, model_validator


class InterestEnum(str, Enum):
    culture = "culture"
    history = "history"
    food = "food"
    nature = "nature"
    adventure = "adventure"
    nightlife = "nightlife"
    relaxation = "relaxation"
    shopping = "shopping"
    art = "art"
    family = "family"
    beaches = "beaches"
    photography = "photography"


class BudgetLevel(str, Enum):
    budget = "budget"
    mid_range = "mid_range"
    luxury = "luxury"


# ---------------------------------------------------------------------------
# Trip planning
# ---------------------------------------------------------------------------
class TripPlanRequest(BaseModel):
    session_id: Optional[str] = Field(
        default=None,
        description="Existing session id to continue a conversation. "
        "Omit to start a brand new planning session.",
    )
    destination: str = Field(..., min_length=2, examples=["Kyoto, Japan"])
    start_date: date = Field(..., examples=["2026-10-10"])
    end_date: date = Field(..., examples=["2026-10-17"])
    travelers: int = Field(default=1, ge=1, le=30)
    budget_amount: float = Field(..., gt=0, description="Total trip budget")
    budget_currency: str = Field(default="USD", min_length=3, max_length=3)
    budget_level: BudgetLevel = Field(default=BudgetLevel.mid_range)
    interests: List[InterestEnum] = Field(default_factory=list)
    origin_city: Optional[str] = Field(
        default=None, description="Departure city, used for transport suggestions"
    )
    additional_notes: Optional[str] = Field(
        default=None,
        max_length=1000,
        description="Dietary restrictions, mobility needs, pace preference, etc.",
    )

    @field_validator("destination", "origin_city")
    @classmethod
    def strip_text(cls, v: Optional[str]) -> Optional[str]:
        return v.strip() if v else v

    @model_validator(mode="after")
    def validate_dates(self) -> "TripPlanRequest":
        if self.end_date <= self.start_date:
            raise ValueError("end_date must be after start_date")
        trip_length = (self.end_date - self.start_date).days
        if trip_length > 60:
            raise ValueError("Trips longer than 60 days are not supported")
        return self

    @property
    def duration_days(self) -> int:
        return (self.end_date - self.start_date).days


class FollowUpRequest(BaseModel):
    session_id: str = Field(..., description="Session id returned by /trip/plan")
    question: str = Field(..., min_length=1, max_length=2000)


class ChatMessage(BaseModel):
    role: str
    content: str


class TripPlanResponse(BaseModel):
    session_id: str
    destination: str
    duration_days: int
    itinerary: str
    tools_used: List[str] = Field(default_factory=list)


class FollowUpResponse(BaseModel):
    session_id: str
    answer: str
    tools_used: List[str] = Field(default_factory=list)


class SessionHistoryResponse(BaseModel):
    session_id: str
    messages: List[ChatMessage]


class HealthResponse(BaseModel):
    status: str
    app_name: str
    version: str
    llm_provider: str
    llm_configured: bool
    mock_apis: bool


class ErrorResponse(BaseModel):
    error: str
    detail: Optional[str] = None
