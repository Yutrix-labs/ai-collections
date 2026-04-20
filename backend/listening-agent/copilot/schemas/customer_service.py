"""Pydantic v2 models for customer service copilot output validation."""

from pydantic import BaseModel, Field, field_validator
from typing import Optional
from enum import Enum


class Priority(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class NextMove(BaseModel):
    points: list[str] = Field(..., min_length=1, max_length=2)
    priority: Priority

    @field_validator("points", mode="before")
    @classmethod
    def truncate_points(cls, v):
        return [p[:50] for p in v]


class Insight(BaseModel):
    type: str   # intent | sentiment | alert | suggestion
    text: str = Field(..., max_length=120)
    priority: Priority


class CopilotResponse(BaseModel):
    next_move: NextMove
    insights: list[Insight] = Field(default_factory=list)


class PreCallSummaryResponse(BaseModel):
    summary: str = Field(..., max_length=500)


class DispositionResult(str, Enum):
    REQUEST_COMPLETED = "Request Completed"
    REQUEST_PENDING = "Request Pending"
    COMPLAINT_REGISTERED = "Complaint Registered"
    ESCALATED = "Escalated"
    FOLLOW_UP_REQUIRED = "Follow-up Required"
    INFORMATION_PROVIDED = "Information Provided"
    NOT_RESOLVED = "Not Resolved"


class NextAction(str, Enum):
    NO_ACTION = "No Action"
    CALLBACK_SCHEDULED = "Callback Scheduled"
    BACKEND_PROCESSING = "Backend Processing"
    SUPERVISOR_REVIEW = "Supervisor Review"
    DOCUMENTATION_REQUIRED = "Documentation Required"
    CROSS_TEAM_HANDOFF = "Cross-team Handoff"


class Disposition(BaseModel):
    result: DispositionResult
    confidence: float = Field(..., ge=0.0, le=1.0)
    notes: str = Field(..., max_length=150)
    nextAction: NextAction
    reasoning: str = Field(..., max_length=100)


class DispositionResponse(BaseModel):
    disposition: Disposition
