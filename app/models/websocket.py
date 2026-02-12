"""
WebSocket message schemas and event types.
"""

from typing import Optional, Any, Dict, List
from pydantic import BaseModel
from enum import Enum


class WebSocketEventType(str, Enum):
    """WebSocket event types."""
    # Server → Client events
    TRANSCRIPT = "transcript"
    INSIGHT = "insight"
    SENTIMENT_UPDATE = "sentiment_update"
    DATA_SURFACE = "data_surface"
    DISPOSITION_PREFILL = "disposition_prefill"
    CALL_STATUS = "call_status"

    # Client → Server events
    REFRESH_INSIGHTS = "refresh_insights"
    DISMISS_INSIGHT = "dismiss_insight"
    ACCEPT_SUGGESTION = "accept_suggestion"
    RESYNC = "resync"


class WebSocketMessage(BaseModel):
    """Base WebSocket message envelope."""
    event: str
    timestamp: str
    payload: Dict[str, Any]


class ClientMessage(BaseModel):
    """Client → Server message."""
    action: str  # "dismiss_insight", "accept_suggestion", "refresh_insights", "resync"
    insight_id: Optional[str] = None
    last_utterance_id: Optional[str] = None
    last_insight_id: Optional[str] = None


class TranscriptPayload(BaseModel):
    """Transcript event payload."""
    utterance_id: str
    speaker: str
    text: str
    call_elapsed: int
    sentiment: Optional[str] = None
    sentiment_score: Optional[float] = None


class InsightPayload(BaseModel):
    """Insight event payload."""
    insight_id: str
    type: str
    text: str
    time: str
    priority: str
    source_layer: str
    related_utterance_ids: List[str] = []


class SentimentUpdatePayload(BaseModel):
    """Sentiment update event payload."""
    overall: str
    trend: str
    score: Optional[float] = None


class DataSurfacePayload(BaseModel):
    """Data surface event payload."""
    trigger_topic: str
    data_type: str
    records: List[Dict[str, Any]]
    summary: str


class DispositionPrefillPayload(BaseModel):
    """Disposition prefill event payload."""
    result: str
    date: Optional[str] = None
    amount: Optional[str] = None
    notes: str
    next_action: str
    confidence: Optional[float] = None


class CallStatusPayload(BaseModel):
    """Call status event payload."""
    status: str
    duration_sec: Optional[int] = None
