# Copilot v2 — Claude Code Implementation Guide

## Overview

You are updating a real-time debt collection copilot system. The copilot runs on every customer turn during a live call, sends a prompt to Claude Haiku on Amazon Bedrock (boto3), and pushes guidance to the agent's UI via Java WebSocket.

This document covers ALL changes to implement. Read fully before writing any code.

---

## Architecture

```
LiveKit (audio/STT) → Python BE (builds prompt, calls Bedrock) → Java API → WebSocket → FE
```

- Python BE calls Bedrock via `boto3` using `invoke_model_with_response_stream`
- Python pushes results to Java via REST API (two separate calls)
- Java pushes to FE via WebSocket (two separate message types)
- Call flows are stored as JSON, converted to TOON format for tabular data in the prompt

---

## Task 1: Replace the Copilot Prompt

### What
Replace the existing verbose prompt (the one with `--- CUSTOMER PROFILE ---`, `--- DISPOSITION SCHEMA ---`, insights array, etc.) with a simplified version.

### New prompt structure
The prompt returns TWO things only:
1. `next_move` — 1-2 bullet point cues (NOT dialogue, NOT full sentences)
2. `disposition` — running call outcome prediction (nullable)

### New prompt builder function

```python
def build_copilot_prompt(customer: dict, loan: dict, additional: dict,
                         payment_lines: list[str], policy_lines: list[str],
                         recent_transcript: list[str], transcript_lines: list[str],
                         call_flow_text: str) -> tuple[str, str]:

    system_prompt = """Real-time debt collection copilot. Return JSON only, no markdown.
{"next_move":{"points":["<50ch each, max 2>"],"priority":"high|medium|low"},"disposition":<obj or null>}
disposition: {"result":"PTP|Won't Pay|Can't Pay|Wrong Number|Invalid Number|Not Reachable|Not Picking","confidence":0.0-1.0,"date":"YYYY-MM-DD|null","amount":number|null,"reason":"Job Loss|Business Loss|Medical Issues|Issues with Bank|Wrong EMI Amount|null","notes":"<150ch","nextAction":"Follow-up Call|Send Payment Link|Escalate to Supervisor|Legal Notice|No Action"}"""

    user_prompt = f"""Customer:{customer.get('name','')} Agr:{customer.get('agreementId','')} Loan:{loan.get('amount','')} Tenure:{loan.get('tenure','')} Type:{customer.get('loanType','')}
Outs:{loan.get('outstanding','')} Overdue:{loan.get('overdue','')} DPD:{additional.get('dpd',0)}d EMI:₹{additional.get('amount','')}
Payments:{'; '.join(payment_lines[-3:])}
Policies:{'; '.join(policy_lines)}
Call Flow:
{call_flow_text}
Transcript:
{chr(10).join(transcript_lines)}
Rules:
- points: 1-2 short bullet cues for the agent. NOT dialogue. NOT sentences. Key talking points only.
- Follow the call flow decision tree to determine appropriate next step.
- Empty transcript = opening strategy bullets based on customer profile + call flow.
- Vague customer = push for specific date + amount.
- Hardship = empathy first, then policy options.
- Committed = confirm date + amount + method.
- Lawyer/dispute/aggression = de-escalate.
- disposition null if <3 exchanges. PTP needs explicit date+amount from customer. confidence>=0.7 only on clear commitment/refusal.
- Use ONLY provided data. Never fabricate."""

    return system_prompt, user_prompt
```

### Key rules
- `system_prompt` and `user_prompt` are returned SEPARATELY. The system prompt goes in Bedrock's `system` field for caching.
- `system_prompt` must be CHARACTER-FOR-CHARACTER identical across all turns in the same call. No dynamic data in it.
- All dynamic data (customer, transcript, flows) goes in `user_prompt` only.
- `call_flow_text` is passed in as a pre-formatted string (see Task 6).
- Remove the old `insights_lines` parameter — insights are gone.
- Remove any `previous insights` tracking — no longer needed.
- `payment_lines[-3:]` — only last 3 payments.

---

## Task 2: Add Pydantic Response Models

### New file: `copilot_schema.py`

```python
from __future__ import annotations

import re
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field, field_validator


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
    points: list[str] = Field(..., min_length=1, max_length=2)
    priority: Priority

    @field_validator("points")
    @classmethod
    def validate_points(cls, v):
        for i, point in enumerate(v):
            if len(point) > 50:
                v[i] = point[:50]
        return v


class Disposition(BaseModel):
    result: DispositionResult
    confidence: float = Field(..., ge=0.0, le=1.0)
    date: Optional[str] = Field(None, pattern=r"^\d{4}-\d{2}-\d{2}$")
    amount: Optional[float] = None
    reason: Optional[str] = None
    notes: str = Field(..., max_length=150)
    nextAction: NextActionType

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

    @field_validator("date", "amount")
    @classmethod
    def validate_ptp_fields(cls, v, info):
        if v is not None and info.data.get("result") != DispositionResult.PTP:
            raise ValueError("date and amount are only valid when result is PTP")
        return v


class CopilotResponse(BaseModel):
    next_move: NextMove
    disposition: Optional[Disposition] = None


def parse_llm_response(raw: str) -> CopilotResponse:
    """Parse LLM output, stripping markdown fences if present."""
    cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw.strip())
    return CopilotResponse.model_validate_json(cleaned)
```

### Integration
Wherever the LLM response is currently parsed, replace with:
```python
try:
    response = parse_llm_response(accumulated_text)
except Exception as e:
    logger.error(f"LLM parse failed: {e}, raw: {accumulated_text[:500]}")
    return None
```

---

## Task 3: Streaming Bedrock Call with Two-Phase Push

### What
Replace `invoke_model()` with `invoke_model_with_response_stream()`. Push `next_move` to Java as soon as it's complete (~800ms), then push `disposition` after full response (~1500ms).

### Streaming implementation

```python
import json
import re
import time

async def call_copilot_llm(system_prompt: str, user_prompt: str, call_id: str, java_api_client):
    body = json.dumps({
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": 300,
        "system": system_prompt,
        "messages": [{"role": "user", "content": user_prompt}],
        "temperature": 0.3
    })

    t_start = time.perf_counter()

    response = bedrock_client.invoke_model_with_response_stream(
        modelId="YOUR_MODEL_ID",  # keep whatever model ID is currently configured
        body=body,
        contentType="application/json"
    )

    t_first_token = None
    accumulated = ""
    next_move_sent = False
    token_count = 0

    for event in response["body"]:
        chunk = json.loads(event["chunk"]["bytes"])

        if chunk.get("type") == "content_block_delta":
            if t_first_token is None:
                t_first_token = time.perf_counter()

            delta_text = chunk.get("delta", {}).get("text", "")
            accumulated += delta_text
            token_count += 1

            # PHASE 1: Push next_move as soon as it's complete
            if not next_move_sent and is_next_move_complete(accumulated):
                t_next_move = time.perf_counter()
                next_move_json = extract_next_move(accumulated)
                if next_move_json:
                    t_push_start = time.perf_counter()
                    await java_api_client.post(
                        f"/copilot/{call_id}/next-move",
                        json=next_move_json
                    )
                    t_push_end = time.perf_counter()
                    next_move_sent = True

                    logger.info(
                        f"[CopilotEngine] ✅ next_move pushed"
                        f" | e2e={int((t_next_move - t_start) * 1000)}ms"
                        f" | push={int((t_push_end - t_push_start) * 1000)}ms"
                        f" | points={next_move_json.get('points', [])}"
                        f" | priority={next_move_json.get('priority')}"
                    )

    t_end = time.perf_counter()

    # PHASE 2: Parse full response, push disposition
    try:
        full_response = parse_llm_response(accumulated)
        if full_response.disposition:
            await java_api_client.post(
                f"/copilot/{call_id}/disposition",
                json=full_response.disposition.model_dump()
            )
    except Exception as e:
        logger.error(f"[CopilotEngine] disposition parse failed: {e}")

    # Timing log
    logger.info(
        f"[CopilotEngine] TIMING"
        f" | ttft={int((t_first_token - t_start) * 1000) if t_first_token else 'N/A'}ms"
        f" | e2e={int((t_end - t_start) * 1000)}ms"
        f" | output_tokens≈{token_count}"
    )

    return full_response


def is_next_move_complete(accumulated: str) -> bool:
    """Check if next_move JSON object is fully streamed."""
    pattern = r'"next_move"\s*:\s*\{"points"\s*:\s*\[.*?\]\s*,\s*"priority"\s*:\s*"[^"]+"\s*\}\s*,'
    return bool(re.search(pattern, accumulated, re.DOTALL))


def extract_next_move(accumulated: str) -> dict | None:
    """Extract the next_move object from partial JSON."""
    match = re.search(
        r'"next_move"\s*:\s*(\{"points"\s*:\s*\[.*?\]\s*,\s*"priority"\s*:\s*"[^"]+"\s*\})',
        accumulated,
        re.DOTALL
    )
    if match:
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError:
            return None
    return None
```

### Important
- `invoke_model_with_response_stream` is synchronous in boto3. If running in async context, wrap in executor:
  ```python
  await asyncio.get_event_loop().run_in_executor(None, sync_function)
  ```
- If regex extraction fails, fall back to waiting for full response (graceful degradation).
- Keep the existing `invoke_model` path behind a feature flag for rollback:
  ```python
  COPILOT_V2_ENABLED = os.getenv("COPILOT_V2_ENABLED", "true").lower() == "true"
  ```

---

## Task 4: Transcript Preprocessing

### What
Limit transcript to last 8 turns. Strip filler words. Skip copilot call on agent-only turns and short acknowledgments.

### Transcript trimming

```python
import re

MAX_TRANSCRIPT_TURNS = 8

FILLER_PATTERNS = re.compile(
    r'\b(um+|uh+|hmm+|okay so|right right|you know|like I said|actually|basically)\b',
    re.IGNORECASE
)

def preprocess_transcript(full_transcript: list[dict], max_turns: int = MAX_TRANSCRIPT_TURNS) -> list[str]:
    recent = full_transcript[-max_turns:]
    lines = []
    for turn in recent:
        role = turn.get("role", "unknown").capitalize()
        text = turn.get("text", "").strip()
        text = FILLER_PATTERNS.sub("", text)
        text = re.sub(r"\s{2,}", " ", text).strip()
        if text:
            lines.append(f"{role}: {text}")
    return lines
```

### Fire-only-on-customer-turns gate

```python
def should_fire_copilot(latest_turn: dict) -> bool:
    role = latest_turn.get("role", "").lower()
    if role != "customer":
        return False
    text = latest_turn.get("text", "").strip()
    if len(text) < 10:
        return False
    return True
```

Wrap the existing copilot trigger:
```python
if should_fire_copilot(latest_turn):
    await call_copilot_llm(...)
```

---

## Task 5: Add TOON Util

### New file: `toon_util.py`

Add the complete `toon_util.py` file from the attached `toon_util.py`. This implements the TOON (Token-Oriented Object Notation) spec for converting JSON to a compact text format.

Key function: `json_to_toon(data)` — converts any Python dict/list to TOON format.

### Where to use TOON
TOON saves ~40-50% tokens on **tabular data** (arrays of uniform objects). Use it ONLY for:
- Payment history data (if passed as structured dicts instead of pre-formatted strings)
- Any other tabular arrays going into the prompt

Do NOT use TOON for:
- Call flows (non-uniform, no savings vs compact text)
- Transcript lines (flat strings, no savings)
- Policy lines (flat strings, no savings)

### Example
```python
from toon_util import json_to_toon

payments = [
    {"date": "2026-01-15", "amount": 12500, "status": "partial", "method": "UPI"},
    {"date": "2026-02-10", "amount": 8000, "status": "partial", "method": "NEFT"},
]
print(json_to_toon({"payments": payments}))
# payments[2]{date,amount,status,method}:
#   2026-01-15,12500,partial,UPI
#   2026-02-10,8000,partial,NEFT
```

---

## Task 6: Call Flow Integration

### New file: `call_flows.json`

```json
{
  "flows": [
    {
      "id": "ptp",
      "name": "Promise to Pay",
      "goal": "Get explicit date + amount + method",
      "steps": [
        "greet → verify identity",
        "if not verified → confirm number → end call",
        "state overdue amount + EMI clearly",
        "if willing → push exact date → exact amount → payment method → confirm all 3 → close",
        "if vague → anchor with date suggestion → offer partial payment → get commitment",
        "if needs time → offer 2-3 day window max → set callback date → confirm"
      ]
    },
    {
      "id": "wrong_number",
      "name": "Wrong Number",
      "goal": "Confirm wrong number, update records, end quickly",
      "steps": [
        "greet → ask for customer by name",
        "if wrong person → confirm phone number → ask if they know customer → apologize → end",
        "if no such person → confirm number → apologize → end",
        "if customer denies identity → do NOT argue → note as possible right party refusal → end politely"
      ]
    },
    {
      "id": "cant_pay_job_loss",
      "name": "Can't Pay — Job Loss",
      "goal": "Show empathy, explore options, escalate if needed",
      "steps": [
        "greet → verify identity → state overdue",
        "on hardship disclosed → empathize, do NOT pressure",
        "explore partial payment → can they pay small amount? → get date + amount",
        "explore restructuring → mention EMI restructuring / moratorium if in policy",
        "if no capacity at all → note hardship reason → set follow-up 2-4 weeks → escalate to supervisor",
        "compliance: never threaten or pressure after hardship disclosed"
      ]
    }
  ]
}
```

### Loading and formatting call flows for the prompt

```python
import json

# Load once at startup
with open("call_flows.json") as f:
    ALL_FLOWS = {flow["id"]: flow for flow in json.load(f)["flows"]}

def get_call_flow_text(flow_id: str) -> str:
    """
    Format a single call flow as compact text for the LLM prompt.
    Returns plain text — NOT TOON (no savings for this data shape).
    """
    flow = ALL_FLOWS.get(flow_id)
    if not flow:
        return ""

    lines = [
        f"Flow: {flow['name']}",
        f"Goal: {flow['goal']}",
        "Steps:"
    ]
    for step in flow["steps"]:
        lines.append(f"  - {step}")

    return "\n".join(lines)


def select_flow_id(customer: dict, additional: dict) -> str:
    """
    Backend selects the most likely flow based on customer profile.
    This is a simple heuristic — expand as needed.
    """
    dpd = additional.get("dpd", 0)

    # Default to PTP — most common call type
    # Add more heuristics as you build more flows
    return "ptp"
```

### Integration into prompt builder
```python
flow_id = select_flow_id(customer, additional)
call_flow_text = get_call_flow_text(flow_id)
system_prompt, user_prompt = build_copilot_prompt(
    customer, loan, additional,
    payment_lines, policy_lines,
    recent_transcript, transcript_lines,
    call_flow_text
)
```

---

## Task 7: Java API Changes

### New REST endpoints (called by Python)

#### `POST /copilot/{callId}/next-move`
```json
{
  "points": ["Get specific date", "Suggest ₹26,000"],
  "priority": "high"
}
```

#### `POST /copilot/{callId}/disposition`
```json
{
  "result": "PTP",
  "confidence": 0.3,
  "date": null,
  "amount": null,
  "reason": null,
  "notes": "Customer willing but no commitment yet",
  "nextAction": "Follow-up Call"
}
```
Disposition body can also be `null`.

### New WebSocket message types (pushed to FE)

#### `copilot:next-move` (arrives first, ~800ms)
```json
{
  "type": "copilot:next-move",
  "callId": "xxx",
  "data": {
    "points": ["Get specific date", "Suggest ₹26,000"],
    "priority": "high"
  }
}
```

#### `copilot:disposition` (arrives second, ~1500ms)
```json
{
  "type": "copilot:disposition",
  "callId": "xxx",
  "data": {
    "result": "PTP",
    "confidence": 0.3,
    "date": null,
    "amount": null,
    "reason": null,
    "notes": "Customer willing but no commitment yet",
    "nextAction": "Follow-up Call"
  }
}
```

### Rules
- Java is a passthrough. Receive from Python, push to FE. No validation needed.
- Keep the old single-push endpoint alive during transition behind a feature flag.
- Deprecate it once v2 is stable.

---

## Task 8: FE Changes

### Remove
- Old insights cards (intent, suggestion, policy, alert, sentiment) — all gone.
- Old single copilot WS message handler.

### Add
Handle two separate WS messages:

1. `copilot:next-move` → Render hero card immediately
   - Show each bullet point from `points` array
   - Color-code by `priority`: high=red/orange, medium=blue, low=gray
   - This card replaces on every new message (not appends)

2. `copilot:disposition` → Update disposition bar below the hero card
   - Show `result` + `confidence` as a pill/badge
   - Show `notes` as subtitle
   - If `data` is null, show "Listening..." or hide

### Layout
```
┌─────────────────────────────────┐
│ ⚡ NEXT MOVE (hero card)        │
│ • Get specific date             │
│ • Suggest ₹26,000              │
│                    priority: ●  │
├─────────────────────────────────┤
│ 📋 PTP | confidence: 0.3       │
│ Customer willing, no commitment │
└─────────────────────────────────┘
```

---

## Task 9: Feature Flag + Rollback

### Add environment variable
```
COPILOT_V2_ENABLED=true
```

### In Python
```python
COPILOT_V2_ENABLED = os.getenv("COPILOT_V2_ENABLED", "true").lower() == "true"

if COPILOT_V2_ENABLED:
    # New: streaming + two-phase push + new prompt
    await call_copilot_llm_v2(...)
else:
    # Old: single invoke_model + single push
    await call_copilot_llm_v1(...)
```

### Rollback
Flip `COPILOT_V2_ENABLED=false` and redeploy. Old path should remain untouched.

---

## Implementation Order

```
Phase 1 — Python only (no Java/FE changes needed to test)
  1. Add copilot_schema.py (Task 2)
  2. Add toon_util.py (Task 5)
  3. Add call_flows.json + loader (Task 6)
  4. Replace prompt builder (Task 1)
  5. Add transcript preprocessing + fire gate (Task 4)
  6. Add feature flag (Task 9)
  → Test: call the new prompt with invoke_model (non-streaming), validate JSON output with Pydantic

Phase 2 — Streaming + Java + FE
  7. Switch to streaming Bedrock call (Task 3)
  8. Add Java endpoints + WS types (Task 7)
  9. Update FE (Task 8)
  → Test: full e2e with streaming, verify two-phase push timing
```

---

## Testing Checklist

### Phase 1
- [ ] New prompt produces valid JSON on 20+ real transcript samples
- [ ] Pydantic validation passes on all LLM outputs
- [ ] `next_move.points` are short cues, NOT dialogue or full sentences
- [ ] `next_move.points` has 1-2 items, each under 50 chars
- [ ] Disposition is null for early conversations (<3 exchanges)
- [ ] PTP disposition only has date/amount when customer explicitly stated both
- [ ] Copilot does NOT fire on agent-only turns
- [ ] Copilot does NOT fire on short customer acknowledgments ("ok", "yes")
- [ ] Call flow text appears in prompt correctly
- [ ] TOON util converts tabular data correctly (test with payment dicts)

### Phase 2
- [ ] Streaming: `next_move` arrives at Java within ~800ms of Bedrock call start
- [ ] Streaming: disposition arrives within ~1500ms
- [ ] Java pushes two separate WS messages correctly
- [ ] FE renders `next_move` card immediately on first WS message
- [ ] FE renders disposition card on second WS message
- [ ] Fallback: if streaming parse fails, full response still processed
- [ ] Feature flag: `COPILOT_V2_ENABLED=false` reverts to old behavior
- [ ] No regressions on existing call flow (LiveKit, STT, etc.)

---

## Example LLM Responses (for testing)

### Turn 1 — Opening
```json
{"next_move":{"points":["Acknowledge partial payments made","Ask what's blocking full EMI"],"priority":"high"},"disposition":null}
```

### Customer is vague
```json
{"next_move":{"points":["Get specific date","Get specific amount — suggest ₹26,000"],"priority":"high"},"disposition":{"result":"PTP","confidence":0.3,"date":null,"amount":null,"reason":null,"notes":"Customer willing but no specific commitment yet","nextAction":"Follow-up Call"}}
```

### Customer hardship — job loss
```json
{"next_move":{"points":["Empathize — acknowledge job loss","Offer EMI restructuring / moratorium"],"priority":"high"},"disposition":{"result":"Can't Pay","confidence":0.6,"date":null,"amount":null,"reason":"Job Loss","notes":"Customer lost job 2 months ago, exploring options","nextAction":"Escalate to Supervisor"}}
```

### Clear PTP obtained
```json
{"next_move":{"points":["Confirm: ₹26,000 by March 5, UPI","Close call positively"],"priority":"medium"},"disposition":{"result":"PTP","confidence":0.9,"date":"2026-03-05","amount":26000,"reason":null,"notes":"Customer committed ₹26,000 by March 5 via UPI","nextAction":"Send Payment Link"}}
```

### Wrong number
```json
{"next_move":{"points":["Apologize and end call"],"priority":"low"},"disposition":{"result":"Wrong Number","confidence":0.95,"date":null,"amount":null,"reason":null,"notes":"Confirmed wrong number","nextAction":"No Action"}}
```

### Customer mentions lawyer
```json
{"next_move":{"points":["De-escalate — no pressure","Acknowledge rights, offer options"],"priority":"high"},"disposition":{"result":"Won't Pay","confidence":0.5,"date":null,"amount":null,"reason":"Issues with Bank","notes":"Customer hostile, mentioned lawyer","nextAction":"Escalate to Supervisor"}}
```

### Routine turn — no new signal
```json
{"next_move":{"points":["Redirect to payment — ask for date"],"priority":"medium"},"disposition":{"result":"PTP","confidence":0.3,"date":null,"amount":null,"reason":null,"notes":"Call ongoing, no commitment yet","nextAction":"Follow-up Call"}}
```
