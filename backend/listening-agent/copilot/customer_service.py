"""Customer Service Copilot — implements BaseCopilot for customer service calls.

Four AI moments:
1. Customer lookup (from local JSON)
2. Pre-call summary (one-shot LLM)
3. Live copilot (streaming LLM per customer turn)
4. Disposition (one-shot LLM on disconnect)
"""

import asyncio
import json
import logging
import os
import re
import time
from pathlib import Path
from typing import Dict, List, Optional

import aiohttp
import boto3

from copilot.base import BaseCopilot
from copilot.schemas.customer_service import (
    CopilotResponse,
    DispositionResponse,
    PreCallSummaryResponse,
)

logger = logging.getLogger(__name__)

DATA_PATH = Path(__file__).parent / "data" / "customer-service.json"

# ── Bedrock model (same as collections) ──────────────────────────────────────
BEDROCK_MODEL_ID = (
    "arn:aws:bedrock:ap-south-1:144918211563:inference-profile/"
    "global.anthropic.claude-haiku-4-5-20251001-v1:0"
)

# ── Prompts ──────────────────────────────────────────────────────────────────

PRECALL_SYSTEM_PROMPT = (
    "You are a customer service AI assistant for a bank. Generate a brief customer "
    "context summary for the agent who is about to take a call. The summary must be "
    "readable in 4-5 seconds — 2-3 sentences max. Prioritize: open issues, red flags, "
    "pending requests, recent activity. Skip anything resolved with no follow-up needed. "
    "Be direct, no filler."
)

COPILOT_SYSTEM_PROMPT = (
    "You are a real-time copilot for a bank customer service agent on a live call. "
    "Your job: tell the agent what to do or ask NEXT.\n\n"
    "OUTPUT:\n"
    "- 1-2 bullet points: actionable steps, clarifying questions, or solutions. Max 50 chars each.\n"
    "- Priority: high (urgent/blocker), medium (important), low (informational).\n\n"
    "BEHAVIOR:\n"
    "- Empty/greeting transcript: suggest opening based on pending items or known issues.\n"
    "- Customer states a problem: suggest resolution steps or clarifying questions to diagnose faster.\n"
    "- Customer is confused: simplify, suggest what to explain.\n"
    "- Multiple open issues exist: address the customer's stated concern first, then suggest surfacing others.\n"
    "- If customer raises something already resolved: confirm resolution and move on.\n"
    "- Use ONLY provided data. Never fabricate."
)

DISPOSITION_SYSTEM_PROMPT = (
    "You are analyzing a completed bank customer service call. Generate the call disposition "
    "based on the full transcript and customer context.\n\n"
    "DISPOSITION RESULTS (pick exactly one):\n"
    "- Request Completed: Customer's request was fully processed\n"
    "- Request Pending: Request initiated but needs backend processing or follow-up\n"
    "- Complaint Registered: New complaint was logged during this call\n"
    "- Escalated: Call was transferred to supervisor or specialist team\n"
    "- Follow-up Required: Customer needs a callback or further action\n"
    "- Information Provided: Agent answered a query, no action needed\n"
    "- Not Resolved: Could not help, needs further investigation\n\n"
    "NEXT ACTIONS (pick exactly one):\n"
    "- No Action | Callback Scheduled | Backend Processing | Supervisor Review | "
    "Documentation Required | Cross-team Handoff\n\n"
    "RULES:\n"
    "- confidence >= 0.8 only when outcome is clear and unambiguous from transcript.\n"
    "- notes: max 150 chars, summarize what happened and outcome.\n"
    "- If transcript is very short or call dropped early, result should be 'Not Resolved' "
    "with low confidence."
)


# ── Helper functions ─────────────────────────────────────────────────────────

def _load_customers() -> dict:
    with open(DATA_PATH) as f:
        return json.load(f)


def _get_customer_by_phone(phone: str) -> Optional[dict]:
    """Look up customer by phone. Normalizes to last 10 digits."""
    customers = _load_customers()
    if not phone:
        return None
    digits = re.sub(r"[^\d]", "", phone)
    normalized = digits[-10:] if len(digits) >= 10 else digits
    return customers.get(normalized)


def _format_loan_summary(loans: list) -> str:
    lines = []
    for loan in loans:
        loan_type = loan.get("loanType", "Unknown")
        status = loan.get("status", "Unknown")
        outstanding = loan.get("outstandingAmount", loan.get("currentOutstanding", 0))
        dpd = loan.get("dpd", 0)
        overdue = loan.get("overdueAmount", 0)
        line = f"{loan_type}: ₹{outstanding:,} outstanding, DPD {dpd}, Status {status}"
        if overdue and overdue > 0:
            line += f", Overdue ₹{overdue:,}"
        lines.append(line)
    return "\n".join(lines)


def _build_precall_user_prompt(customer: dict) -> str:
    active_complaints = [c for c in customer.get("complaints", []) if c.get("status") != "Resolved"]
    return (
        f"--- CUSTOMER ---\n"
        f"Name: {customer['profile']['name']}\n"
        f"Segment: {customer['profile']['segment']} | "
        f"Relationship: ₹{customer['profile']['relationshipValue']:,}\n"
        f"Customer Since: {customer['profile']['customerSince']}\n\n"
        f"--- LOANS ---\n{json.dumps(customer['loans'], indent=2)}\n\n"
        f"--- COLLECTIONS ---\n{json.dumps(customer['collections'], indent=2)}\n\n"
        f"--- RECENT INTERACTIONS (last 3) ---\n"
        f"{json.dumps(customer['interactionHistory'][:3], indent=2)}\n\n"
        f"--- ACTIVE COMPLAINTS ---\n{json.dumps(active_complaints, indent=2)}\n\n"
        f"--- PENDING REQUESTS ---\n{json.dumps(customer['pendingRequests'], indent=2)}\n\n"
        f"Generate a 2-3 sentence summary. Focus on what the agent NEEDS to know before the call."
    )


def _build_copilot_user_prompt(customer: dict, precall_summary: str, transcript: list) -> str:
    transcript_lines = [f"{t['role'].upper()}: {t['text']}" for t in transcript[-8:]]
    active_complaints = [c for c in customer.get("complaints", []) if c.get("status") != "Resolved"]

    collections = customer.get("collections", {})
    collections_line = (
        f"Status: {collections.get('collectionStatus')}, Overdue: ₹{collections.get('totalOverdue', 0):,}"
        if collections.get("isInCollections")
        else "No overdue."
    )

    return (
        f"--- CONTEXT ---\n"
        f"Customer: {customer['profile']['name']} | Segment: {customer['profile']['segment']}\n"
        f"Phone: {customer['profile']['phone']}\n\n"
        f"--- PRE-CALL SUMMARY ---\n{precall_summary}\n\n"
        f"--- ACTIVE COMPLAINTS ---\n{json.dumps(active_complaints, indent=2)}\n\n"
        f"--- PENDING REQUESTS ---\n{json.dumps(customer['pendingRequests'], indent=2)}\n\n"
        f"--- LOANS (summary) ---\n{_format_loan_summary(customer['loans'])}\n\n"
        f"--- COLLECTIONS ---\nIn Collections: {collections.get('isInCollections')}\n"
        f"{collections_line}\n\n"
        f"--- TRANSCRIPT (last {len(transcript_lines)} turns) ---\n"
        f"{chr(10).join(transcript_lines) if transcript_lines else 'No conversation yet.'}\n\n"
        f'Respond with JSON only:\n'
        f'{{"next_move": {{"points": ["<point 1, max 50 chars>", "<point 2, max 50 chars>"], '
        f'"priority": "high|medium|low"}}}}'
    )


def _build_disposition_user_prompt(customer: dict, precall_summary: str, transcript: list) -> str:
    # Trim transcript: first 3 + last 20 turns
    if len(transcript) > 23:
        trimmed = transcript[:3] + transcript[-20:]
    else:
        trimmed = transcript
    transcript_lines = [f"{t['role'].upper()}: {t['text']}" for t in trimmed]

    return (
        f"--- CUSTOMER ---\n"
        f"Name: {customer['profile']['name']} | Segment: {customer['profile']['segment']}\n\n"
        f"--- PRE-CALL SUMMARY ---\n{precall_summary}\n\n"
        f"--- FULL TRANSCRIPT ---\n{chr(10).join(transcript_lines)}\n\n"
        f'Respond with JSON only:\n'
        f'{{"disposition": {{"result": "<one of the valid results>", "confidence": 0.0-1.0, '
        f'"notes": "<max 150 chars>", "nextAction": "<one of the valid next actions>", '
        f'"reasoning": "<why this disposition, max 100 chars>"}}}}'
    )


# ── Streaming helpers ────────────────────────────────────────────────────────

_NEXT_MOVE_PATTERN = re.compile(r'"next_move"\s*:\s*\{[^{}]*\}\s*', re.DOTALL)


def _is_next_move_complete(accumulated: str) -> bool:
    return bool(_NEXT_MOVE_PATTERN.search(accumulated))


def _extract_next_move(accumulated: str) -> Optional[dict]:
    """Extract next_move JSON from partial streaming output."""
    match = re.search(r'"next_move"\s*:\s*(\{[^{}]*\})', accumulated, re.DOTALL)
    if not match:
        return None
    try:
        return json.loads(match.group(1))
    except json.JSONDecodeError:
        return None


# ── Main copilot class ───────────────────────────────────────────────────────

class CustomerServiceCopilot(BaseCopilot):
    """Customer Service copilot with 4 AI moments."""

    def __init__(self, call_sid: str, http_session, mobile_number: str | None = None):
        self.call_sid = call_sid
        self.http_session = http_session
        self.mobile_number = mobile_number
        self.backend_url = os.getenv("BACKEND_URL", "http://localhost:8080")
        self.aws_region = os.getenv("AWS_REGION", "ap-south-1")

        # State
        self.customer_data: Optional[dict] = None
        self.precall_summary: Optional[str] = None
        self.transcript: List[Dict] = []
        self._llm_lock = asyncio.Lock()
        self._bedrock_client = None

    def _get_bedrock_client(self):
        if self._bedrock_client is None:
            self._bedrock_client = boto3.client(
                "bedrock-runtime",
                region_name=self.aws_region,
                aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
                aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
            )
        return self._bedrock_client

    # ── AI Moment 1 & 2: Initialize (customer lookup + pre-call summary) ─────

    async def initialize(self):
        """Look up customer by phone, push context to FE, generate pre-call summary."""
        self.customer_data = _get_customer_by_phone(self.mobile_number)

        if self.customer_data:
            logger.info(f"Customer found | callSid={self.call_sid} name={self.customer_data['profile']['name']}")
            await self._push_customer_context()
            await self._generate_and_push_precall_summary()
        else:
            logger.warn(f"Customer not found | callSid={self.call_sid} mobile={self.mobile_number}")
            # Push null context so FE knows customer wasn't found
            await self._push_to_java(
                f"/collassistantapi/copilot/{self.call_sid}/customer-context",
                {"callSid": self.call_sid, "mobileNumber": self.mobile_number, "customerData": None},
            )

    async def _push_customer_context(self):
        """Push full customer data to Java → WS → FE."""
        await self._push_to_java(
            f"/collassistantapi/copilot/{self.call_sid}/customer-context",
            {
                "callSid": self.call_sid,
                "mobileNumber": self.mobile_number,
                "customerData": self.customer_data,
            },
        )
        logger.info(f"Customer context pushed | callSid={self.call_sid}")

    async def _generate_and_push_precall_summary(self):
        """AI Moment 2: Generate pre-call summary via one-shot LLM call."""
        if not self.customer_data:
            return

        user_prompt = _build_precall_user_prompt(self.customer_data)
        start = time.monotonic()

        try:
            response = await self._call_bedrock_oneshot(
                system_prompt=PRECALL_SYSTEM_PROMPT,
                user_prompt=user_prompt,
                max_tokens=300,
            )

            # Parse — LLM may return JSON or plain text
            try:
                parsed = json.loads(response)
                self.precall_summary = parsed.get("summary", response)
            except json.JSONDecodeError:
                self.precall_summary = response.strip()

            latency = (time.monotonic() - start) * 1000
            logger.info(
                f"Pre-call summary generated | callSid={self.call_sid} "
                f"latency={latency:.0f}ms len={len(self.precall_summary)}"
            )

            await self._push_to_java(
                f"/collassistantapi/copilot/{self.call_sid}/summary",
                {
                    "callSid": self.call_sid,
                    "mobileNumber": self.mobile_number,
                    "summary": self.precall_summary,
                },
            )

        except Exception as e:
            logger.error(f"Pre-call summary failed | callSid={self.call_sid} error={e}")

    # ── AI Moment 3: Live copilot (per customer turn) ────────────────────────

    async def process_utterance(self, speaker: str, text: str, timestamp: str):
        """Called for every transcript turn. Fires copilot on customer turns."""
        self.transcript.append({"role": speaker, "text": text, "time": timestamp})

        # Only fire on customer turns with meaningful content
        if speaker != "customer" or len(text.strip()) < 10:
            return

        # Skip if another LLM call is in progress
        if self._llm_lock.locked():
            logger.debug(f"Skipping copilot — LLM lock held | callSid={self.call_sid}")
            return

        async with self._llm_lock:
            await self._generate_and_push_next_move()

    async def _generate_and_push_next_move(self):
        """Stream Bedrock to generate next_move, push as soon as JSON completes."""
        if not self.customer_data:
            return

        user_prompt = _build_copilot_user_prompt(
            self.customer_data,
            self.precall_summary or "No pre-call summary available.",
            self.transcript,
        )
        start = time.monotonic()

        try:
            accumulated = await self._call_bedrock_streaming(
                system_prompt=COPILOT_SYSTEM_PROMPT,
                user_prompt=user_prompt,
                on_next_move_ready=self._push_next_move,
                max_tokens=200,
            )

            latency = (time.monotonic() - start) * 1000
            logger.info(f"Live copilot completed | callSid={self.call_sid} latency={latency:.0f}ms")

        except Exception as e:
            logger.error(f"Live copilot failed | callSid={self.call_sid} error={e}")

    async def _push_next_move(self, next_move_data: dict):
        """Push next_move to Java via existing endpoint."""
        payload = {
            "callSid": self.call_sid,
            "mobileNumber": self.mobile_number,
            "points": next_move_data.get("points", []),
            "priority": next_move_data.get("priority", "medium"),
        }
        await self._push_to_java(f"/collassistantapi/copilot/{self.call_sid}/next-move", payload)
        logger.info(f"Next move pushed | callSid={self.call_sid} priority={payload['priority']}")

    # ── AI Moment 4: Disposition (on disconnect) ─────────────────────────────

    async def on_call_end(self):
        """Generate disposition from full transcript and push to Java."""
        if not self.transcript:
            logger.warn(f"No transcript for disposition | callSid={self.call_sid}")
            return

        user_prompt = _build_disposition_user_prompt(
            self.customer_data or {"profile": {"name": "Unknown", "segment": "Unknown"}, "collections": {}},
            self.precall_summary or "No pre-call summary available.",
            self.transcript,
        )
        start = time.monotonic()

        try:
            response = await self._call_bedrock_oneshot(
                system_prompt=DISPOSITION_SYSTEM_PROMPT,
                user_prompt=user_prompt,
                max_tokens=300,
            )

            # Parse disposition JSON
            cleaned = response.strip()
            if cleaned.startswith("```"):
                cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
                cleaned = re.sub(r"\s*```$", "", cleaned)

            parsed = json.loads(cleaned)
            disposition = parsed.get("disposition", parsed)

            latency = (time.monotonic() - start) * 1000
            logger.info(
                f"Disposition generated | callSid={self.call_sid} "
                f"result={disposition.get('result')} latency={latency:.0f}ms"
            )

            # Push to Java via disposition endpoint
            await self._push_to_java(
                f"/collassistantapi/copilot/{self.call_sid}/disposition",
                {
                    "callSid": self.call_sid,
                    "mobileNumber": self.mobile_number,
                    "data": {
                        "result": disposition.get("result"),
                        "confidence": disposition.get("confidence", 0.5),
                        "notes": disposition.get("notes", ""),
                        "nextAction": disposition.get("nextAction", "No Action"),
                        "reason": disposition.get("reasoning"),
                    },
                },
            )

        except Exception as e:
            logger.error(f"Disposition generation failed | callSid={self.call_sid} error={e}")

    # ── Bedrock LLM methods ──────────────────────────────────────────────────

    async def _call_bedrock_oneshot(self, system_prompt: str, user_prompt: str, max_tokens: int = 300) -> str:
        """Non-streaming Bedrock call for one-shot tasks (pre-call summary, disposition)."""
        client = self._get_bedrock_client()
        body = json.dumps({
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": max_tokens,
            "system": [{"type": "text", "text": system_prompt}],
            "messages": [{"role": "user", "content": [{"type": "text", "text": user_prompt}]}],
        })

        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(
            None,
            lambda: client.invoke_model(modelId=BEDROCK_MODEL_ID, body=body, contentType="application/json"),
        )

        result = json.loads(response["body"].read())
        return result["content"][0]["text"]

    async def _call_bedrock_streaming(
        self,
        system_prompt: str,
        user_prompt: str,
        on_next_move_ready=None,
        max_tokens: int = 200,
    ) -> str:
        """Streaming Bedrock call with early push when next_move JSON completes."""
        client = self._get_bedrock_client()
        body = json.dumps({
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": max_tokens,
            "system": [
                {"type": "text", "text": system_prompt, "cache_control": {"type": "ephemeral"}},
            ],
            "messages": [{"role": "user", "content": [{"type": "text", "text": user_prompt}]}],
        })

        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(
            None,
            lambda: client.invoke_model_with_response_stream(
                modelId=BEDROCK_MODEL_ID, body=body, contentType="application/json"
            ),
        )

        accumulated = ""
        next_move_pushed = False

        for event in response["body"]:
            chunk = event.get("chunk")
            if not chunk:
                continue
            payload = json.loads(chunk["bytes"])

            if payload.get("type") == "content_block_delta":
                delta = payload.get("delta", {})
                text = delta.get("text", "")
                accumulated += text

                # Early push: detect next_move completion
                if not next_move_pushed and _is_next_move_complete(accumulated):
                    nm = _extract_next_move(accumulated)
                    if nm and on_next_move_ready:
                        next_move_pushed = True
                        await on_next_move_ready(nm)

        # Final push if streaming didn't trigger it
        if not next_move_pushed and on_next_move_ready:
            nm = _extract_next_move(accumulated)
            if nm:
                await on_next_move_ready(nm)

        return accumulated

    # ── HTTP helper ──────────────────────────────────────────────────────────

    async def _push_to_java(self, path: str, payload: dict):
        """POST JSON to Java backend."""
        url = f"{self.backend_url}{path}"
        try:
            async with self.http_session.post(
                url, json=payload, timeout=aiohttp.ClientTimeout(total=5)
            ) as resp:
                if resp.status != 200:
                    body = await resp.text()
                    logger.warning(f"Backend returned {resp.status} for {path}: {body}")
        except Exception as e:
            logger.error(f"Failed to POST {path}: {e}")
