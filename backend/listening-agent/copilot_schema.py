"""
Pydantic v2 models for validating and parsing LLM copilot output.
Used by InsightEngine to validate the v2 schema before pushing to Java.
"""

from __future__ import annotations

import json
import re
from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field, field_validator, model_validator


class Priority(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class DispositionResult(str, Enum):
    PTP = "PTP"
    WONT_PAY = "Won't Pay"
    CANT_PAY = "Can't Pay"
    WRONG_NUMBER = "Wrong Number"
    INVALID_NUMBER = "Invalid Number"
    NOT_REACHABLE = "Not Reachable"
    NOT_PICKING = "Not Picking"


class NextActionType(str, Enum):
    FOLLOW_UP_CALL = "Follow-up Call"
    SEND_PAYMENT_LINK = "Send Payment Link"
    ESCALATE_TO_SUPERVISOR = "Escalate to Supervisor"
    LEGAL_NOTICE = "Legal Notice"
    NO_ACTION = "No Action"


CANT_PAY_REASONS = {"Job Loss", "Business Loss", "Medical Issues"}
WONT_PAY_REASONS = {"Issues with Bank", "Wrong EMI Amount"}


class NextMove(BaseModel):
    action: str = Field(..., max_length=250)
    phrase: Optional[str] = Field(None, max_length=500)
    priority: Priority

    @model_validator(mode="before")
    @classmethod
    def normalize_keys(cls, data: any) -> any:
        if isinstance(data, dict):
            # LLM prompt uses "points" (list) → join into "action" string
            if "points" in data and "action" not in data:
                pts = data.pop("points")
                data["action"] = "; ".join(pts) if isinstance(pts, list) else str(pts)
            # Normalize "mid" priority to "medium"
            if data.get("priority") == "mid":
                data["priority"] = "medium"
        return data


class ContextualDetail(BaseModel):
    label: str = Field(..., max_length=100)
    value: str = Field(..., max_length=200)
    highlight: bool = False


class Disposition(BaseModel):
    result: Optional[DispositionResult] = None
    confidence: float = Field(0.0, ge=0.0, le=1.0)
    date: Optional[str] = Field(None, pattern=r"^\d{4}-\d{2}-\d{2}$")
    amount: Optional[float] = None
    reason: Optional[str] = None
    notes: str = Field("", max_length=500)
    nextAction: NextActionType = NextActionType.NO_ACTION

    @model_validator(mode="before")
    @classmethod
    def normalize_keys(cls, data: any) -> any:
        if isinstance(data, dict):
            # LLM prompt uses compressed keys → map to full names
            if "conf" in data and "confidence" not in data:
                data["confidence"] = data.pop("conf") or 0.0
            elif "confidence" in data and data["confidence"] is None:
                data["confidence"] = 0.0
            if "next" in data and "nextAction" not in data:
                raw = data.pop("next")
                # Map short values like "Follow-up" → "Follow-up Call"
                SHORT_MAP = {
                    "Follow-up": "Follow-up Call",
                    "Link": "Send Payment Link",
                    "Supervisor": "Escalate to Supervisor",
                    "Legal": "Legal Notice",
                    "None": "No Action",
                }
                data["nextAction"] = SHORT_MAP.get(raw, raw)
            if "amt" in data and "amount" not in data:
                data["amount"] = data.pop("amt")
        return data

    @field_validator("reason")
    @classmethod
    def validate_reason(cls, v, info):
        if v is None:
            return v
        result = info.data.get("result")
        if result == DispositionResult.CANT_PAY and v not in CANT_PAY_REASONS:
            raise ValueError(f"Can't Pay reason must be one of {CANT_PAY_REASONS}")
        if result == DispositionResult.WONT_PAY and v not in WONT_PAY_REASONS:
            raise ValueError(f"Won't Pay reason must be one of {WONT_PAY_REASONS}")
        return v

    @field_validator("date", "amount", mode="before")
    @classmethod
    def validate_ptp_fields(cls, v, info):
        # Only PTP should have date/amount — other results must leave them null.
        # We validate leniently here (don't raise) to avoid breaking on early turns.
        return v

    @model_validator(mode="after")
    def check_ptp_fields(self) -> "Disposition":
        if self.result != DispositionResult.PTP:
            if self.date is not None or self.amount is not None:
                # Silently clear non-PTP date/amount rather than raising
                object.__setattr__(self, "date", None)
                object.__setattr__(self, "amount", None)
        return self


class Insight(BaseModel):
    type: str
    text: str
    priority: str
    reasoning: Optional[str] = None


class CopilotResponse(BaseModel):
    next_move: NextMove
    contextual_details: Optional[list[ContextualDetail]] = Field(
        None, alias="contextual_details_list"
    )
    disposition: Optional[Disposition] = None
    insights: List[Insight] = []

    @model_validator(mode="before")
    @classmethod
    def wrap_contextual_details(cls, data: any) -> any:
        if isinstance(data, dict) and "contextual_details" in data:
            details = data.pop("contextual_details")
            if isinstance(details, dict) and "details" in details:
                data["contextual_details_list"] = details["details"]
        return data


def parse_llm_response(raw: str) -> CopilotResponse:
    """
    Parse LLM output into a validated CopilotResponse.
    Strips markdown fences if present, then validates with Pydantic.
    Raises ValidationError on bad output.
    """
    # cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw.strip(), flags=re.MULTILINE)
    # cleaned = cleaned.strip()

    # 🔥 Improved cleaning
    cleaned = re.sub(r"```(?:json)?", "", raw, flags=re.IGNORECASE)  # remove ```json anywhere
    cleaned = cleaned.replace("```", "").strip()

    # Extract only JSON block (fix trailing text issue)
    match = re.search(r"\{.*\}", cleaned, re.DOTALL)
    if match:
        cleaned = match.group(0).strip()
    return CopilotResponse.model_validate_json(cleaned)


def is_next_move_complete(accumulated: str) -> bool:
    """
    Check if the next_move JSON object is fully streamed.
    Looks for the closing brace of next_move followed by a comma or end.
    Works because next_move is always the FIRST field in the output.
    """
    pattern = r'"next_move"\s*:\s*\{[^{}]*\}\s*,'
    return bool(re.search(pattern, accumulated))


def extract_next_move(accumulated: str) -> dict | None:
    """Extract the next_move object from partially accumulated JSON.
    Returns the raw dict (with 'points' list) for the push to Java."""
    match = re.search(r'"next_move"\s*:\s*(\{[^{}]*\})', accumulated)
    if match:
        try:
            raw = json.loads(match.group(1))
            # Basic validation: must have points or action, and priority
            if ("points" in raw or "action" in raw) and "priority" in raw:
                return raw
        except Exception:
            return None
    return None


def is_contextual_details_complete(accumulated: str) -> bool:
    """Check if the contextual_details JSON object is fully streamed."""
    # Matches "contextual_details": { "details": [...] }
    pattern = r'"contextual_details"\s*:\s*\{[^{}]*"details"\s*:\s*\[[^\]]*\]\s*\}'
    return bool(re.search(pattern, accumulated))


def extract_contextual_details(accumulated: str) -> dict | None:
    """Extract contextual_details object from partially accumulated JSON."""
    pattern = r'"contextual_details"\s*:\s*(\{[^{}]*"details"\s*:\s*\[[^\]]*\]\s*\})'
    match = re.search(pattern, accumulated)
    if match:
        try:
            raw = json.loads(match.group(1))
            # Validate items
            if "details" in raw and isinstance(raw["details"], list):
                valid_details = []
                for d in raw["details"]:
                    valid_details.append(
                        ContextualDetail.model_validate(d).model_dump()
                    )
                return {"details": valid_details}
        except Exception:
            return None
    return None
