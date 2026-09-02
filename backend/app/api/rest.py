"""
REST API endpoints.
"""

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import Optional, List
from app.models.call import CallContext, Insight, InsightType, PriorityLevel, SourceLayer
from app.utils.redis_client import redis_client, get_profile_key
from app.services.ai_insights_engine import trigger_insight_generation
import json


router = APIRouter()


# Mock data for development
MOCK_CALL_CONTEXT = {
    "call_id": "demo-call-123",
    "customer": {
        "name": "Rajesh Kumar Sharma",
        "mobile": "XXXX-XXX-210",
        "email": "r***a@gmail.com",
        "agreement_id": "PL-2024-00847391",
        "loan_type": "Personal Loan"
    },
    "loan": {
        "amount": 850000,
        "tenure_months": 48,
        "emi_start": "15-Mar-2023",
        "emi_end": "15-Feb-2027",
        "outstanding": 485320,
        "overdue": 73800,
        "loan_type": "Personal Loan"
    },
    "additional": {
        "installment_no": "22 of 48",
        "due_date": "15-Jan-2026",
        "amount": 18450,
        "bounce_charges": 1500,
        "penal_charges": 3240,
        "dpd": 67,
        "emi_amount": 18450
    },
    "payment_history": [
        {"date": "2025-12-20", "amount": 5000, "channel": "UPI", "status": "credited"},
        {"date": "2025-11-15", "amount": 18450, "channel": "ECS", "status": "bounced", "bounce_reason": "Insufficient funds"},
        {"date": "2025-10-15", "amount": 18450, "channel": "ECS", "status": "bounced", "bounce_reason": "Insufficient funds"},
        {"date": "2025-09-16", "amount": 18450, "channel": "ECS", "status": "credited"},
        {"date": "2025-08-15", "amount": 18450, "channel": "ECS", "status": "credited"},
        {"date": "2025-07-15", "amount": 18450, "channel": "ECS", "status": "credited"},
    ],
    "past_communications": [
        {"date": "28-Jan", "caller": "Priya M.", "summary": "Callback req. Job change."},
        {"date": "15-Jan", "caller": "Amit R.", "summary": "No answer. SMS sent."},
        {"date": "02-Jan", "caller": "Priya M.", "summary": "₹ 10K PTP Jan 10. Not rcvd."},
        {"date": "20-Dec", "caller": "Amit R.", "summary": "Agreed month-end. ₹ 5K paid."},
    ],
    "initial_insights": [
        {
            "insight_id": "static-1",
            "call_id": "demo-call-123",
            "insight_type": "alert",
            "text": "DPD 67 — DO NOT mention legal action",
            "priority": "high",
            "source_layer": "policy",
            "call_elapsed_ms": 0,
            "time": "0:00"
        },
        {
            "insight_id": "static-2",
            "call_id": "demo-call-123",
            "insight_type": "alert",
            "text": "Broken PTP from Jan 10 — ₹ 10,000 not received",
            "priority": "high",
            "source_layer": "policy",
            "call_elapsed_ms": 0,
            "time": "0:00"
        },
        {
            "insight_id": "static-3",
            "call_id": "demo-call-123",
            "insight_type": "policy",
            "text": "Penalty waiver up to 50% for commitments ≥ ₹ 50,000",
            "priority": "medium",
            "source_layer": "policy",
            "call_elapsed_ms": 0,
            "time": "0:00"
        }
    ],
    "active_policies": {
        "penalty_waiver": {"max_percent": 50, "min_commitment": 50000},
        "settlement_eligible": False,
        "legal_reference_allowed": False
    }
}


@router.get("/calls/{call_id}/context")
async def get_call_context(call_id: str):
    """
    Get full customer context at call start.
    Returns customer profile, loan details, payment history, and initial insights.
    """

    # Try to fetch from Redis cache
    profile_key = get_profile_key(call_id)
    cached_context = await redis_client.get_json(profile_key)

    if cached_context:
        return cached_context

    # For demo, return mock data
    # In production, fetch from database
    context = MOCK_CALL_CONTEXT.copy()
    context["call_id"] = call_id

    # Cache in Redis
    await redis_client.set(profile_key, context, ex=3600)

    return context


class InsightGenerationRequest(BaseModel):
    """Request to generate insights."""
    call_id: str
    trigger: str  # "agent_refresh" | "end_of_call"


@router.post("/insights/generate")
async def generate_insights_endpoint(request: InsightGenerationRequest):
    """
    Manually trigger AI insight generation.
    Called when agent clicks "Refresh Insights" or call ends.
    """

    # Enqueue insight generation job
    await trigger_insight_generation(request.call_id, request.trigger)

    return {"status": "queued", "call_id": request.call_id, "trigger": request.trigger}


class AgentActionRequest(BaseModel):
    """Agent action on insights."""
    action: str  # "dismiss_insight" | "accept_suggestion"
    insight_id: Optional[str] = None


@router.post("/calls/{call_id}/agent-action")
async def agent_action(call_id: str, request: AgentActionRequest):
    """
    Handle agent actions on insights (dismiss, accept).
    """

    if request.action == "dismiss_insight":
        # Store dismissal (could update database)
        print(f"Insight {request.insight_id} dismissed")

    elif request.action == "accept_suggestion":
        # Store acceptance (could update database)
        print(f"Insight {request.insight_id} accepted")

    return {"status": "success", "action": request.action}


@router.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "service": "AI Collections Assistant API"}


# ============================================
# TEST ENDPOINTS (for development/testing)
# ============================================

class TestUtteranceRequest(BaseModel):
    """Test utterance for simulating calls."""
    call_id: str
    speaker: str  # "agent" | "customer"
    text: str
    call_elapsed_ms: int
    sentiment: Optional[str] = None


@router.post("/test/utterance")
async def add_test_utterance(request: TestUtteranceRequest):
    """
    Add a test utterance to Redis stream (for testing without STT).
    This simulates what would come from Deepgram/LiveKit.
    """
    from app.utils.redis_client import get_transcript_stream_key
    import uuid

    utterance = {
        "utterance_id": str(uuid.uuid4()),
        "call_id": request.call_id,
        "speaker": request.speaker,
        "text": request.text,
        "call_elapsed_ms": request.call_elapsed_ms,
        "sentiment": request.sentiment or "neutral",
        "is_final": True
    }

    # Add to transcript stream
    stream_key = get_transcript_stream_key(request.call_id)
    msg_id = await redis_client.xadd(stream_key, utterance)

    return {
        "status": "added",
        "stream_key": stream_key,
        "message_id": msg_id,
        "utterance": utterance
    }


@router.get("/test/streams/{call_id}")
async def get_test_streams(call_id: str):
    """View all streams for a call (for debugging)."""
    from app.utils.redis_client import (
        get_transcript_stream_key,
        get_insights_stream_key,
        get_insight_jobs_stream_key
    )

    transcript_key = get_transcript_stream_key(call_id)
    insights_key = get_insights_stream_key(call_id)
    jobs_key = get_insight_jobs_stream_key(call_id)

    # Read from streams
    transcripts = []
    insights = []
    jobs = []

    try:
        transcript_msgs = await redis_client.client.xread({transcript_key: "0"}, count=100)
        if transcript_msgs:
            for stream, msg_list in transcript_msgs:
                for msg_id, data in msg_list:
                    transcripts.append({"id": msg_id, "data": data})

        insight_msgs = await redis_client.client.xread({insights_key: "0"}, count=100)
        if insight_msgs:
            for stream, msg_list in insight_msgs:
                for msg_id, data in msg_list:
                    insights.append({"id": msg_id, "data": data})

        job_msgs = await redis_client.client.xread({jobs_key: "0"}, count=100)
        if job_msgs:
            for stream, msg_list in job_msgs:
                for msg_id, data in msg_list:
                    jobs.append({"id": msg_id, "data": data})
    except Exception as e:
        return {"error": str(e)}

    return {
        "call_id": call_id,
        "transcripts": transcripts,
        "insights": insights,
        "insight_jobs": jobs
    }
