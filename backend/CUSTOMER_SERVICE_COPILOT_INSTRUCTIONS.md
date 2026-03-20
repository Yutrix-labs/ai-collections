# Customer Service AI Copilot — Implementation Instructions

## Overview

We are adding a new **Customer Service** use case to the existing Loan Collection Call Copilot system. The existing collections flow must remain completely untouched — zero regression. A toggle mechanism switches between use cases at deployment level.

---

## Current Architecture (Collections)

```
Customer Call → LiveKit (SIP) → Python BE (Deepgram STT → Claude Haiku on Bedrock)
                                    ├── POST /copilot/{callId}/next-move → Java → WS → FE
                                    └── POST /copilot/{callId}/disposition → Java → WS → FE
```

- Python handles STT + LLM calls via boto3 (streaming Bedrock).
- Java is a passthrough — receives from Python, pushes to FE via WebSocket.
- Collections copilot fires on every customer turn, outputs `next_move` (points + priority) and `disposition`.
- `next_move` is pushed first (~800ms), disposition follows (~1500ms).
- All logic currently lives in a single file.

---

## Target Architecture (Customer Service)

Same pipeline, three distinct AI moments instead of one continuous copilot:

```
Call Connects → LiveKit SIP event (phone number)
    │
    ├─ 1. CUSTOMER LOOKUP
    │     Python matches phone number against customers.json
    │     Pushes start event + full static customer data to Java → WS → FE
    │     FE renders Customer Insight Panel (raw data cards)
    │
    ├─ 2. PRE-CALL SUMMARY (one-shot LLM call)
    │     Input: Full customer context (profile, loans, collections, interactions, complaints, pending requests)
    │     Output: Short paragraph (4-5 second read)
    │     Pushed to FE via Java WS
    │     Agent reads while greeting the customer
    │
    ├─ 3. LIVE COPILOT (fires on every customer turn)
    │     Input: Customer context + pre-call summary + transcript (last N turns)
    │     Output: next_move (points + priority) — solution-oriented guidance
    │     Pushed to FE via Java WS (same /copilot/{callId}/next-move endpoint)
    │
    └─ 4. DISPOSITION (one-shot on disconnect)
         Input: Full transcript + customer context
         Output: Disposition result + notes + next action
         Triggered by LiveKit disconnect event
         Pushed to FE via Java WS (same /copilot/{callId}/disposition endpoint)
```

---

## Toggle Mechanism

### Environment Variable

```env
COPILOT_MODE=customer_service   # or "collections"
```

### Factory Pattern

A factory function reads `COPILOT_MODE` from env and returns the correct handler. Both use cases implement the same abstract interface so the calling code (LiveKit event handlers, transcript update callbacks) doesn't change.

```python
# copilot/base.py — Abstract interface

class BaseCopilot(ABC):

    @abstractmethod
    async def on_call_start(self, phone_number: str) -> dict:
        """
        Called when call connects.
        Returns customer data + any pre-call AI output.
        """
        pass

    @abstractmethod
    async def on_customer_turn(self, transcript: list[dict], context: dict) -> dict:
        """
        Called after each customer turn.
        Returns next_move guidance.
        """
        pass

    @abstractmethod
    async def on_call_end(self, transcript: list[dict], context: dict) -> dict:
        """
        Called on disconnect event.
        Returns disposition.
        """
        pass
```

```python
# copilot/factory.py

import os
from copilot.collections import CollectionsCopilot
from copilot.customer_service import CustomerServiceCopilot

def get_copilot() -> BaseCopilot:
    mode = os.getenv("COPILOT_MODE", "collections")
    if mode == "customer_service":
        return CustomerServiceCopilot()
    elif mode == "collections":
        return CollectionsCopilot()
    else:
        raise ValueError(f"Unknown COPILOT_MODE: {mode}")
```

### Collections copilot migration

Move the existing single-file collections logic into `copilot/collections.py`, implementing the `BaseCopilot` interface. The internal logic, prompts, schemas, and behavior must remain identical — this is purely a structural refactor, not a functional change.

For collections:
- `on_call_start`: Returns customer data (existing behavior, however it works today).
- `on_customer_turn`: Runs the existing streaming Bedrock call with the collections prompt. Two-phase push (next_move then disposition) — exactly as it works now.
- `on_call_end`: Collections currently generates disposition during the call (every turn), not at call end. So this can be a no-op or just log the final disposition.

**Critical: Do NOT modify any collections prompt text, schema, streaming logic, or post-processing. Only wrap it in the new interface.**

---

## File Structure

```
copilot/
├── base.py                        # Abstract BaseCopilot interface
├── factory.py                     # Reads COPILOT_MODE, returns correct handler
├── collections.py                 # Existing collections logic (moved here, wrapped in BaseCopilot)
├── customer_service.py            # New customer service logic (implements BaseCopilot)
├── schemas/
│   ├── collections.py             # Existing Pydantic models (moved here, untouched)
│   └── customer_service.py        # New Pydantic models for customer service
└── data/
    └── customers.json             # Mock customer data (phone number keyed)
```

---

## Customer Data Lookup

### Source

`copilot/data/customers.json` — keyed by phone number (string). Contains: profile, loans, collections status, interaction history, complaints, pending requests.

### Lookup Logic

When a call connects, LiveKit provides the caller's phone number from the SIP event. Python loads the JSON file and looks up the customer by phone number.

```python
import json
from pathlib import Path

DATA_PATH = Path(__file__).parent / "data" / "customers.json"

def load_customers() -> dict:
    with open(DATA_PATH) as f:
        return json.load(f)

def get_customer_by_phone(phone: str) -> dict | None:
    customers = load_customers()
    # Strip country code if present (e.g., +91)
    normalized = phone.lstrip("+").lstrip("91") if phone.startswith("+91") or phone.startswith("91") else phone
    return customers.get(normalized)
```

If customer not found, the copilot should still work — push a "Customer not found" status to FE and run the live copilot without customer context (generic guidance mode).

---

## Customer Service Prompts

### Prompt 1: Pre-Call Summary

This runs ONCE when the call connects and the customer is identified. It produces a short, scannable paragraph the agent can read in 4-5 seconds.

```python
PRECALL_SYSTEM_PROMPT = """You are a customer service AI assistant for a bank. Generate a brief customer context summary for the agent who is about to take a call. The summary must be readable in 4-5 seconds — 2-3 sentences max. Prioritize: open issues, red flags, pending requests, recent activity. Skip anything resolved with no follow-up needed. Be direct, no filler."""

def build_precall_user_prompt(customer: dict) -> str:
    return f"""--- CUSTOMER ---
Name: {customer['profile']['name']}
Segment: {customer['profile']['segment']} | Relationship: ₹{customer['profile']['relationshipValue']:,}
Customer Since: {customer['profile']['customerSince']}

--- LOANS ---
{json.dumps(customer['loans'], indent=2)}

--- COLLECTIONS ---
{json.dumps(customer['collections'], indent=2)}

--- RECENT INTERACTIONS (last 3) ---
{json.dumps(customer['interactionHistory'][:3], indent=2)}

--- ACTIVE COMPLAINTS ---
{json.dumps([c for c in customer['complaints'] if c['status'] != 'Resolved'], indent=2)}

--- PENDING REQUESTS ---
{json.dumps(customer['pendingRequests'], indent=2)}

Generate a 2-3 sentence summary. Focus on what the agent NEEDS to know before the call."""
```

**Expected output:**

```json
{
  "summary": "Platinum customer (₹35L relationship, since 2017). Has a pending address update stuck on Aadhaar OTP verification from March 10. All loans current, no complaints."
}
```

### Prompt 2: Live Copilot (Per Customer Turn)

Fires after every customer turn. Outputs `next_move` — solution-oriented guidance, clarifying questions to ask, or actions to take. Same output shape as collections (`points` + `priority`) so FE rendering doesn't change.

```python
COPILOT_SYSTEM_PROMPT = """You are a real-time copilot for a bank customer service agent on a live call. Your job: tell the agent what to do or ask NEXT.

OUTPUT:
- 1-2 bullet points: actionable steps, clarifying questions, or solutions. Max 50 chars each.
- Priority: high (urgent/blocker), medium (important), low (informational).

BEHAVIOR:
- Empty/greeting transcript: suggest opening based on pending items or known issues.
- Customer states a problem: suggest resolution steps or clarifying questions to diagnose faster.
- Customer is confused: simplify, suggest what to explain.
- Multiple open issues exist: address the customer's stated concern first, then suggest surfacing others.
- If customer raises something already resolved: confirm resolution and move on.
- Use ONLY provided data. Never fabricate."""

def build_copilot_user_prompt(customer: dict, precall_summary: str, transcript: list[dict]) -> str:
    transcript_lines = [f"{t['role'].upper()}: {t['text']}" for t in transcript[-8:]]

    return f"""--- CONTEXT ---
Customer: {customer['profile']['name']} | Segment: {customer['profile']['segment']}
Phone: {customer['profile']['phone']}

--- PRE-CALL SUMMARY ---
{precall_summary}

--- ACTIVE COMPLAINTS ---
{json.dumps([c for c in customer['complaints'] if c['status'] != 'Resolved'], indent=2)}

--- PENDING REQUESTS ---
{json.dumps(customer['pendingRequests'], indent=2)}

--- LOANS (summary) ---
{_format_loan_summary(customer['loans'])}

--- COLLECTIONS ---
In Collections: {customer['collections']['isInCollections']}
{f"Status: {customer['collections']['collectionStatus']}, Overdue: ₹{customer['collections']['totalOverdue']:,}" if customer['collections']['isInCollections'] else "No overdue."}

--- TRANSCRIPT (last {len(transcript_lines)} turns) ---
{chr(10).join(transcript_lines) if transcript_lines else "No conversation yet."}

Respond with JSON only:
{{
  "next_move": {{
    "points": ["<point 1, max 50 chars>", "<point 2, max 50 chars>"],
    "priority": "high|medium|low"
  }}
}}"""
```

**Helper for loan summary (keep it compact for token efficiency):**

```python
def _format_loan_summary(loans: list[dict]) -> str:
    lines = []
    for loan in loans:
        loan_type = loan.get('loanType', 'Unknown')
        status = loan.get('status', 'Unknown')
        outstanding = loan.get('outstandingAmount', loan.get('currentOutstanding', 0))
        dpd = loan.get('dpd', 0)
        overdue = loan.get('overdueAmount', 0)
        line = f"{loan_type}: ₹{outstanding:,} outstanding, DPD {dpd}, Status {status}"
        if overdue > 0:
            line += f", Overdue ₹{overdue:,}"
        lines.append(line)
    return chr(10).join(lines)
```

**Expected output examples:**

Early call (customer just said "I want to update my email"):
```json
{
  "next_move": {
    "points": ["Verify identity via OTP or security Q", "Ask for new email address"],
    "priority": "medium"
  }
}
```

Customer mentions overdue loan concern:
```json
{
  "next_move": {
    "points": ["Acknowledge concern, pull up loan details", "Check if restructuring options apply"],
    "priority": "high"
  }
}
```

### Prompt 3: Disposition (At Call End)

Fires ONCE on LiveKit disconnect event. Generates the final call disposition from the full transcript.

```python
DISPOSITION_SYSTEM_PROMPT = """You are analyzing a completed bank customer service call. Generate the call disposition based on the full transcript and customer context.

DISPOSITION RESULTS (pick exactly one):
- Request Completed: Customer's request was fully processed (email update, address change, info provided, etc.)
- Request Pending: Request initiated but needs backend processing or follow-up
- Complaint Registered: New complaint was logged during this call
- Escalated: Call was transferred to supervisor or specialist team
- Follow-up Required: Customer needs a callback or further action
- Information Provided: Agent answered a query, no action needed
- Not Resolved: Could not help, needs further investigation

NEXT ACTIONS (pick exactly one):
- No Action: Issue fully resolved
- Callback Scheduled: Agent to call back at agreed time
- Backend Processing: Request sent to back office
- Supervisor Review: Needs manager attention
- Documentation Required: Customer needs to submit documents
- Cross-team Handoff: Another department needs to handle this

RULES:
- confidence >= 0.8 only when outcome is clear and unambiguous from transcript.
- notes: max 150 chars, summarize what happened and outcome.
- If transcript is very short or call dropped early, result should be "Not Resolved" with low confidence."""

def build_disposition_user_prompt(customer: dict, precall_summary: str, transcript: list[dict]) -> str:
    transcript_lines = [f"{t['role'].upper()}: {t['text']}" for t in transcript]

    return f"""--- CUSTOMER ---
Name: {customer['profile']['name']} | Segment: {customer['profile']['segment']}

--- PRE-CALL SUMMARY ---
{precall_summary}

--- FULL TRANSCRIPT ---
{chr(10).join(transcript_lines)}

Respond with JSON only:
{{
  "disposition": {{
    "result": "<one of the valid results>",
    "confidence": 0.0-1.0,
    "notes": "<max 150 chars>",
    "nextAction": "<one of the valid next actions>",
    "reasoning": "<why this disposition, max 100 chars>"
  }}
}}"""
```

---

## Output Schemas (Pydantic)

```python
# copilot/schemas/customer_service.py

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


class CopilotResponse(BaseModel):
    next_move: NextMove


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
```

---

## Java / WebSocket Changes

### No new endpoints needed.

The customer service copilot uses the SAME Java endpoints as collections:

- `POST /copilot/{callId}/next-move` — same payload shape (points + priority)
- `POST /copilot/{callId}/disposition` — different payload fields but same endpoint

### New WS message type needed:

**Pre-call summary** — this is new. Java needs one additional endpoint and WS message type:

```
POST /copilot/{callId}/summary
Body:
{
  "summary": "Platinum customer (₹35L relationship). Pending address update stuck on Aadhaar OTP..."
}
```

Java pushes to FE:
```json
{
  "type": "copilot:summary",
  "callId": "xxx",
  "data": {
    "summary": "Platinum customer (₹35L relationship). Pending address update stuck on Aadhaar OTP..."
  }
}
```

### Static customer data push:

On call start, push the full customer data for the FE to render the Customer Insight Panel. This can go through the existing start event mechanism or a new endpoint:

```
POST /copilot/{callId}/customer-context
Body: { full customer JSON from customers.json }
```

Java pushes:
```json
{
  "type": "copilot:customer-context",
  "callId": "xxx",
  "data": { ... full customer object ... }
}
```

---

## FE Changes

### Customer Insight Panel (static data)

On receiving `copilot:customer-context`, render cards showing:
- **Profile**: Name, segment, relationship value, customer since, KYC status
- **Loans**: Each loan with type, outstanding, EMI, DPD, status (color-coded: green=active, red=overdue)
- **Active Complaints**: Complaint ID, category, status, description
- **Pending Requests**: Request type, status, details
- **Recent Interactions**: Last 3 interactions with date, topic, status

This is raw data display, not AI-generated.

### Pre-call Summary

On receiving `copilot:summary`, render a highlighted text block above the copilot cards. Short paragraph, always visible. Style it as a "Context" or "Overview" banner.

### Live Copilot

On receiving `copilot:next-move`, render exactly as collections does — same component, same styling. The content is different (service guidance instead of collection strategy) but the shape is identical.

### Disposition

On receiving `copilot:disposition`, render the disposition card. Different enum values than collections but same visual structure: result as a badge, notes as subtitle, nextAction as a secondary label.

---

## Streaming & Latency

### Pre-call summary
- Non-streaming is fine. This is a one-shot call at call start. Agent is greeting the customer during this time.
- Expected latency: ~1-2 seconds. Acceptable since the agent has the static data immediately.

### Live copilot
- Use the SAME streaming approach as collections: `invoke_model_with_response_stream`, parse `next_move` from partial JSON as soon as it's complete, push immediately.
- Target: next_move visible to agent within ~800ms of customer finishing speaking.

### Disposition
- Non-streaming. Fires on disconnect. No real-time pressure.
- Full transcript can be long — consider trimming to last 20 turns + first 3 turns (captures opening and recent context).

---

## Bedrock Call Configuration

Same model and region as collections:
- Model: Claude Haiku on Bedrock (same model ID)
- Region: Same as current (ap-south-1 or whichever is configured)
- System prompt caching: Yes — system prompts for all three calls are static (no dynamic data in system prompt). All dynamic data goes in user prompt.

---

## Implementation Order

```
Phase 1 — Structural refactor (no new functionality)
├── Create copilot/ directory structure
├── Create base.py with BaseCopilot interface
├── Move existing collections logic into copilot/collections.py
│   └── Wrap in BaseCopilot interface — NO changes to internal logic
├── Create copilot/factory.py
├── Update the LiveKit event handlers / transcript callbacks to use factory
├── Add COPILOT_MODE=collections to env
└── TEST: Collections flow works exactly as before. Zero regression.

Phase 2 — Customer service copilot
├── Add customers.json to copilot/data/
├── Implement customer lookup by phone number
├── Create copilot/schemas/customer_service.py (Pydantic models)
├── Create copilot/customer_service.py implementing BaseCopilot:
│   ├── on_call_start: lookup customer, call pre-call summary LLM, push both to Java
│   ├── on_customer_turn: build copilot prompt with context + summary + transcript, stream to Bedrock, push next_move
│   └── on_call_end: build disposition prompt with full transcript, call Bedrock, push disposition
├── Add pre-call summary prompt
├── Add live copilot prompt
├── Add disposition prompt
└── TEST: Switch COPILOT_MODE=customer_service and verify all three AI moments work.

Phase 3 — Java + FE
├── Java: Add POST /copilot/{callId}/summary endpoint + copilot:summary WS type
├── Java: Add POST /copilot/{callId}/customer-context endpoint + copilot:customer-context WS type
├── FE: Render Customer Insight Panel from copilot:customer-context
├── FE: Render pre-call summary banner from copilot:summary
├── FE: Verify next-move and disposition rendering works with new content
└── TEST: End-to-end flow with both use cases.
```

---

## Testing Checklist

### Collections (Regression)
- [ ] Set COPILOT_MODE=collections
- [ ] Existing collections flow works identically — prompts, schemas, streaming, two-phase push
- [ ] No changes to collections prompt text or output schema
- [ ] FE renders collections copilot exactly as before

### Customer Service — Pre-call Summary
- [ ] Call connects, customer identified by phone number
- [ ] Static customer data pushed to FE and rendered
- [ ] Pre-call summary generated and pushed to FE within ~2 seconds
- [ ] Summary is 2-3 sentences, scannable in 4-5 seconds
- [ ] Summary highlights open issues, pending requests, red flags
- [ ] Unknown phone number → graceful fallback (no crash, "Customer not found" status)

### Customer Service — Live Copilot
- [ ] Fires on every customer turn (not agent turns)
- [ ] Skips very short acknowledgments (<10 chars)
- [ ] next_move points are solution-oriented (not collections-focused)
- [ ] Pre-call summary context is included — insights don't repeat
- [ ] Transcript trimmed to last 8 turns
- [ ] next_move arrives at FE within ~800ms
- [ ] Points are under 50 chars each

### Customer Service — Disposition
- [ ] Fires on LiveKit disconnect event
- [ ] Disposition result is one of the valid customer service enums
- [ ] Notes are under 150 chars
- [ ] confidence >= 0.8 only for clear outcomes
- [ ] Short/dropped calls → "Not Resolved" with low confidence

### Toggle
- [ ] Switching COPILOT_MODE between "collections" and "customer_service" correctly loads the right handler
- [ ] Invalid COPILOT_MODE value → clear error on startup
- [ ] No cross-contamination of prompts or schemas between modes
