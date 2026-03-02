"""
Data models for calls, utterances, and insights.
"""

from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
from enum import Enum


class SpeakerType(str, Enum):
    """Speaker type enum."""
    AGENT = "agent"
    CUSTOMER = "customer"


class SentimentType(str, Enum):
    """Sentiment type enum."""
    POSITIVE = "positive"
    NEUTRAL = "neutral"
    NEGATIVE = "negative"


class InsightType(str, Enum):
    """Insight type enum."""
    INTENT = "intent"
    SUGGESTION = "suggestion"
    POLICY = "policy"
    ALERT = "alert"
    SENTIMENT = "sentiment"


class PriorityLevel(str, Enum):
    """Priority level enum."""
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class SourceLayer(str, Enum):
    """Source layer enum for insights."""
    POLICY = "policy"
    TRIGGER = "trigger"
    LLM = "llm"


class Utterance(BaseModel):
    """Utterance data model."""
    utterance_id: str
    call_id: str
    speaker: SpeakerType
    text: str
    timestamp_ms: int
    call_elapsed_sec: int
    sentiment: Optional[SentimentType] = None
    sentiment_score: Optional[float] = Field(default=None, ge=-1.0, le=1.0)
    confidence: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    is_final: bool = True
    created_at: Optional[datetime] = None


class Insight(BaseModel):
    """Insight data model."""
    insight_id: str
    call_id: str
    insight_type: InsightType
    text: str
    priority: PriorityLevel
    source_layer: SourceLayer
    call_elapsed_ms: int
    time: str  # Formatted time like "0:38"
    reasoning: Optional[str] = None
    related_utterance_ids: List[str] = Field(default_factory=list)
    embedding: Optional[List[float]] = None
    agent_action: Optional[str] = None  # "dismissed", "accepted", None
    created_at: Optional[datetime] = None


class Call(BaseModel):
    """Call data model."""
    call_id: str
    customer_id: str
    agreement_id: str
    agent_id: str
    start_time: datetime
    end_time: Optional[datetime] = None
    status: str = "active"  # "active", "ended", "disconnected"
    duration_sec: Optional[int] = None


class CustomerInfo(BaseModel):
    """Customer information."""
    name: str
    mobile: str
    email: Optional[str] = None
    agreement_id: str
    loan_type: str


class LoanInfo(BaseModel):
    """Loan information."""
    amount: int
    tenure_months: int
    emi_start: str
    emi_end: str
    outstanding: int
    overdue: int
    loan_type: str


class AdditionalInfo(BaseModel):
    """Additional loan details."""
    installment_no: str
    due_date: str
    amount: int
    bounce_charges: int
    penal_charges: int
    dpd: int
    emi_amount: int


class PaymentRecord(BaseModel):
    """Payment history record."""
    date: str
    amount: int
    channel: str  # "ECS", "UPI", "NEFT", "CASH", "NACH"
    status: str  # "credited", "bounced", "reversed", "pending"
    reference_id: Optional[str] = None
    bounce_reason: Optional[str] = None


class CommunicationRecord(BaseModel):
    """Past communication record."""
    date: str
    caller: str
    summary: str


class PolicyRules(BaseModel):
    """Active policy rules."""
    penalty_waiver: Optional[Dict[str, Any]] = None
    settlement_eligible: bool = False
    legal_reference_allowed: bool = False
    hardship_options: Optional[List[str]] = None


class CallContext(BaseModel):
    """Full call context returned at call start."""
    call_id: str
    customer: CustomerInfo
    loan: LoanInfo
    additional: AdditionalInfo
    payment_history: List[PaymentRecord]
    past_communications: List[CommunicationRecord]
    initial_insights: List[Insight]
    active_policies: PolicyRules


class SentimentTimeline(BaseModel):
    """Sentiment timeline point."""
    call_id: str
    call_elapsed_ms: int
    speaker: SpeakerType
    sentiment: SentimentType
    sentiment_score: float
    overall_trend: Optional[str] = None  # "improving", "stable", "declining"


class DispositionData(BaseModel):
    """Disposition form auto-fill data."""
    result: str
    date: Optional[str] = None
    amount: Optional[str] = None
    notes: str
    next_action: str
    confidence: Optional[float] = None
