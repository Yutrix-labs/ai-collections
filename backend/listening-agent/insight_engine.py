"""
AI Insight Engine - In-memory version for listening agent.
Ports logic from app/services/ai_insights_engine.py, transcript_aggregator.py, and prompt_builder.py.
No Redis - all state maintained per-call instance.

v2: Simplified two-output copilot (next_move + disposition only).
    Streaming Bedrock support for early next_move push (~800ms).
    Two-phase push: /copilot/{callId}/next-move then /copilot/{callId}/disposition.
    Pydantic validation via copilot_schema.py.
"""

import asyncio
import hashlib
import json
import logging
import os
import re
import time
from datetime import datetime
from typing import Callable, Dict, List, Optional

from call_flow_loader import format_flow_text, select_flow
from toon_util import json_to_toon

# Suppress noisy third-party debug logs
logging.getLogger("hpack.hpack").setLevel(logging.WARNING)
logging.getLogger("hpack.table").setLevel(logging.WARNING)
logging.getLogger("cerebras.cloud.sdk").setLevel(logging.WARNING)
logging.getLogger("cerebras.cloud.sdk._base_client").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)
logging.getLogger("httpx").setLevel(logging.WARNING)

# ── Transcript preprocessing constants ─────────────────────────────────────
MAX_TRANSCRIPT_TURNS = 8

LANGUAGE_NAMES = {
    "en": "English",
    "hi": "Hindi",
    "mr": "Marathi",
}

FILLER_PATTERNS = re.compile(
    r"\b(um+|uh+|hmm+|okay so|right right|you know|like I said|actually|basically)\b",
    re.IGNORECASE,
)

# Feature flag: set COPILOT_V2_ENABLED=false to fall back to old single-push flow
COPILOT_V2_ENABLED = os.getenv("COPILOT_V2_ENABLED", "true").lower() == "true"

def _pct(p) -> str:
    """Render a 0-1 probability as a rounded percentage (e.g. 0.83 -> '83%')."""
    return f"{round(p * 100)}%" if p is not None else "?"


def format_prediction(prediction: Optional[Dict]) -> str:
    """Compact one-liner of the ML scores for the LLM prompt: PTP-fulfilment plus the
    15-day and 30-day payment probabilities. Empty string when no prediction is available."""
    if not prediction or prediction.get("probability") is None:
        return ""
    parts = [f"PTP-fulfil {_pct(prediction.get('probability'))} ({prediction.get('band', '?')})"]
    p15 = prediction.get("payment_probability_15d") or {}
    if p15.get("probability") is not None:
        parts.append(f"pay-in-15d {_pct(p15.get('probability'))} ({p15.get('band', '?')})")
    p30 = prediction.get("payment_probability_30d") or {}
    if p30.get("probability") is not None:
        parts.append(f"pay-in-30d {_pct(p30.get('probability'))} ({p30.get('band', '?')})")
    return " | ".join(parts)

# ── Cerebras JSON schema for structured output ────────────────────────────
# Mirrors the compressed keys the LLM prompt instructs (points, conf, amt, next).
# Pydantic normalizes these to full field names after parsing.
_CEREBRAS_RESPONSE_FORMAT = {
    "type": "json_schema",
    "json_schema": {
        "name": "copilot_response",
        "schema": {
            "type": "object",
            "properties": {
                "next_move": {
                    "type": "object",
                    "properties": {
                        "points": {
                            "type": "array",
                            "items": {"type": "string"},
                            "minItems": 1,
                            "maxItems": 2,
                        },
                        "priority": {
                            "type": "string",
                            "enum": ["high", "medium", "low"],
                        },
                    },
                    "required": ["points", "priority"],
                    "additionalProperties": False,
                },
                "contextual_details": {
                    "anyOf": [
                        {"type": "null"},
                        {
                            "type": "object",
                            "properties": {
                                "details": {
                                    "type": "array",
                                    "items": {
                                        "type": "object",
                                        "properties": {
                                            "label": {"type": "string", "maxLength": 18},
                                            "value": {"type": "string", "maxLength": 20},
                                            "highlight": {"type": "boolean"},
                                        },
                                        "required": ["label", "value", "highlight"],
                                        "additionalProperties": False,
                                    },
                                    "minItems": 1,
                                    "maxItems": 5,
                                }
                            },
                            "required": ["details"],
                            "additionalProperties": False,
                        },
                    ]
                },
                "insights": {
                    "anyOf": [
                        {"type": "null"},
                        {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "type": {
                                        "type": "string",
                                        "enum": ["intent", "suggestion", "policy", "alert", "sentiment"],
                                    },
                                    "text": {"type": "string", "maxLength": 250},
                                    "priority": {
                                        "type": "string",
                                        "enum": ["high", "medium", "low"],
                                    },
                                    "reasoning": {"type": "string"},
                                },
                                "required": ["type", "text", "priority"],
                                "additionalProperties": False,
                            },
                            "maxItems": 3,
                        },
                    ]
                },
                "disposition": {
                    "anyOf": [
                        {"type": "null"},
                        {
                            "type": "object",
                            "properties": {
                                "result": {
                                    "type": "string",
                                    "enum": [
                                        "PTP",
                                        "Won't Pay",
                                        "Can't Pay",
                                        "Wrong Number",
                                        "Invalid Number",
                                        "Not Reachable",
                                        "Not Picking",
                                    ],
                                },
                                "conf": {"type": "number", "minimum": 0.0, "maximum": 1.0},
                                "date": {
                                    "anyOf": [
                                        {"type": "null"},
                                        {"type": "string", "pattern": r"^\d{4}-\d{2}-\d{2}$"},
                                    ]
                                },
                                "amt": {"anyOf": [{"type": "null"}, {"type": "number"}]},
                                "reason": {"anyOf": [{"type": "null"}, {"type": "string"}]},
                                "notes": {"type": "string", "maxLength": 150},
                                "next": {
                                    "type": "string",
                                    "enum": ["Follow-up", "Link", "Supervisor", "Legal", "None"],
                                },
                            },
                            "required": ["result", "conf", "date", "amt", "reason", "notes", "next"],
                            "additionalProperties": False,
                        },
                    ]
                },
            },
            "required": ["next_move", "contextual_details", "insights", "disposition"],
            "additionalProperties": False,
        },
    },
}

# ── Latency Optimization Helpers ──────────────────────────────────────────

# At module level, track per call
_system_prompt_hash_per_call = {}


def verify_cache_consistency(call_id: str, system_prompt: str):
    """(A1) Detect mid-call prompt changes that break model caching."""
    h = hashlib.md5(system_prompt.encode()).hexdigest()[:8]
    prev = _system_prompt_hash_per_call.get(call_id)
    if prev and prev != h:
        print(
            f"[CopilotEngine] 🚨 CACHE BREAK! system_prompt changed mid-call. prev={prev} new={h}"
        )
    _system_prompt_hash_per_call[call_id] = h


def should_include_disposition(count: int, latest_utterance: str) -> bool:
    """(B1) Determine if this turn should generate a disposition (every 3rd turn or on keyword)."""
    if count == 1:
        return True  # Always first turn
    if count % 3 == 0:
        return True

    text = latest_utterance.lower()
    # Keywords that suggest a shift in disposition
    triggers = [
        "pay",
        "refuse",
        "can't",
        "cant",
        "wont",
        "won't",
        "number",
        "job",
        "lost",
        "busy",
        "call back",
    ]
    return any(t in text for t in triggers)


# ── Pure utility functions ──────────────────────────────────────────────────


def classify_sentiment(text: str) -> str:
    """Rule-based sentiment classification."""
    text_lower = text.lower()

    negative_words = [
        "cannot",
        "can't",
        "won't",
        "don't",
        "never",
        "no",
        "not",
        "problem",
        "issue",
        "difficult",
        "hard",
        "impossible",
        "angry",
        "frustrated",
        "upset",
    ]
    positive_words = [
        "yes",
        "okay",
        "sure",
        "will",
        "can",
        "able",
        "help",
        "thank",
        "appreciate",
        "good",
        "great",
        "understand",
        "agree",
        "reasonable",
    ]

    neg = sum(1 for w in negative_words if w in text_lower)
    pos = sum(1 for w in positive_words if w in text_lower)

    if pos > neg:
        return "positive"
    elif neg > pos:
        return "negative"
    return "neutral"


def detect_topics(text: str) -> List[str]:
    """Rule-based keyword matching for topic detection."""
    topics = []
    t = text.lower()

    if any(
        kw in t
        for kw in ["paid", "payment", "already paid", "sent money", "transferred"]
    ):
        topics.append("payment_history")
    if any(kw in t for kw in ["bounce", "ecs failed", "auto-debit failed", "returned"]):
        topics.append("bounce")
    if any(
        kw in t for kw in ["penalty", "charges", "fee", "extra amount", "why so much"]
    ):
        topics.append("charges")
    if any(kw in t for kw in ["settle", "one-time", "lump sum", "close the loan"]):
        topics.append("settlement")
    if any(
        kw in t
        for kw in ["lost job", "medical", "hospital", "salary cut", "business loss"]
    ):
        topics.append("hardship")
    if any(
        kw in t for kw in ["legal", "lawyer", "court", "consumer forum", "ombudsman"]
    ):
        topics.append("legal")
    if any(
        kw in t for kw in ["wrong amount", "not my loan", "fraud", "already closed"]
    ):
        topics.append("dispute")

    return topics


def preprocess_transcript(
    full_transcript: List[Dict], max_turns: int = MAX_TRANSCRIPT_TURNS
) -> List[str]:
    """
    Trim transcript to last N turns and clean filler words.

    Args:
        full_transcript: List of dicts with 'speaker', 'text', 'time' keys.
        max_turns: Maximum number of turns to include.

    Returns:
        List of formatted transcript lines ready for the prompt.
    """
    recent = full_transcript[-max_turns:]
    lines = []
    for turn in recent:
        speaker = turn.get("speaker", "unknown")
        text = turn.get("text", "").strip()
        time_str = turn.get("time", "")

        # Strip filler words
        text = FILLER_PATTERNS.sub("", text)
        # Collapse multiple spaces
        text = re.sub(r"\s{2,}", " ", text).strip()

        if not text:
            continue

        speaker_label = "AGENT" if speaker == "agent" else "CUSTOMER"
        lines.append(f"[{time_str}] {speaker_label}: {text}")

    return lines


def should_fire_copilot(speaker: str, text: str) -> bool:
    """
    Only fire the copilot LLM when the customer has said something meaningful.
    Skips agent turns and short customer acknowledgments ("okay", "yes", "hmm").

    Args:
        speaker: 'customer' or 'agent'
        text: The utterance text.

    Returns:
        True if copilot should fire.
    """
    if speaker != "customer":
        return False
    # Skip very short utterances: "okay", "yes", "hmm" — not worth an LLM call
    if len(text.strip()) < 10:
        return False
    return True


def format_time(call_elapsed_ms: int) -> str:
    """Format time as MM:SS."""
    seconds = call_elapsed_ms // 1000
    minutes = seconds // 60
    secs = seconds % 60
    return f"{minutes}:{secs:02d}"


# ── Legacy prompt builder (kept for COPILOT_V2_ENABLED=false path) ──────────


def build_llm_prompt(
    profile: Dict,
    transcript: List[Dict],
    previous_insights: List[Dict],
    max_transcript_lines: int = 8,
) -> str:
    """Legacy single-string prompt builder. Used when COPILOT_V2_ENABLED=false."""
    customer = profile.get("customer", {})
    preferred_language = customer.get("preferredLanguage", "en")
    language_name = LANGUAGE_NAMES.get(preferred_language, "English")
    loan = profile.get("loan", {})
    additional = profile.get("additional", {})
    payment_history = profile.get("payment_history", [])
    active_policies = profile.get("active_policies", [])

    payment_lines = []
    for payment in payment_history[-4:]:
        month = payment.get("month", "")
        status = payment.get("status", "")
        amount = payment.get("amount", 0)
        due_amount = payment.get("dueAmount", 0)
        payment_lines.append(f"{month}: CHF {amount:,} / CHF {due_amount:,} ({status})")

    policy_lines = []
    for policy in active_policies:
        policy_name = policy.get("policy", "")
        rule = policy.get("rule", "")
        policy_lines.append(f"- {policy_name}: {rule}")

    recent_transcript = (
        transcript[-max_transcript_lines:]
        if len(transcript) > max_transcript_lines
        else transcript
    )
    transcript_lines = []
    for utterance in recent_transcript:
        speaker = utterance.get("speaker", "unknown")
        text = utterance.get("text", "")
        time_str = utterance.get("time", "")
        sentiment = utterance.get("sentiment", "")
        speaker_label = "AGENT" if speaker == "agent" else "CUSTOMER"
        sentiment_label = (
            f" ({sentiment})" if sentiment and speaker == "customer" else ""
        )
        transcript_lines.append(
            f"[{time_str}] {speaker_label}{sentiment_label}: {text}"
        )

    insights_lines = []
    if previous_insights:
        for insight in previous_insights:
            time_str = insight.get("time", "")
            insight_type = insight.get("type", "")
            priority = insight.get("priority", "")
            text = insight.get("text", "")
            insights_lines.append(f'[{time_str}] {insight_type}/{priority}: "{text}"')
    else:
        insights_lines.append("(none)")

    prediction_line = format_prediction(profile.get("prediction"))
    ml_section = f"\n--- ML PROBABILITIES ---\n{prediction_line}\n" if prediction_line else ""

    prompt = f"""--- CUSTOMER PROFILE ---
Name: {customer.get("name", "")}
Agreement: {customer.get("agreementId", "")} | Loan Type: {customer.get("loanType", "")}
Loan: {loan.get("amount", "")} | Tenure: {loan.get("tenure", "")}
Outstanding: {loan.get("outstanding", "")} | Overdue: {loan.get("overdue", "")}
DPD: {additional.get("dpd", 0)} days | EMI Amount: CHF {additional.get("amount", "")}
{ml_section}
--- PAYMENT HISTORY (recent) ---
{chr(10).join(payment_lines)}

--- ACTIVE POLICY RULES ---
{chr(10).join(policy_lines)}

--- RECENT CONVERSATION (last {len(recent_transcript)} turns) ---
{chr(10).join(transcript_lines)}

--- PREVIOUS INSIGHTS THIS CALL ---
{chr(10).join(insights_lines)}

--- DISPOSITION SCHEMA ---
Valid disposition results and their required fields:
- PTP (Promise to Pay): requires date, amount
- Won't Pay: requires reason (Issues with Bank | Wrong EMI Amount)
- Can't Pay: requires reason (Job Loss | Business Loss | Medical Issues)
- Wrong Number: no additional fields
- Invalid Number: no additional fields
- Not Reachable: no additional fields
- Not Picking: no additional fields

--- INSTRUCTIONS ---
Generate 1-3 NEW insights AND a disposition recommendation (if sufficient conversation data exists).
Treat the ML PROBABILITIES section as a strong signal: PTP-fulfil is the likelihood the customer keeps a promise to pay; pay-in-15d/30d are the likelihood of payment within that window. Low PTP-fulfil → firmer recommendations and lower confidence on a PTP disposition; high PTP-fulfil → support a PTP path. Align any proposed timeline with pay-in-15d/30d. Never state the raw percentages to the customer — use them only to shape insights, suggestions, and disposition.

PART 1 — INSIGHTS:
Each insight must be one of: intent, suggestion, policy, alert, sentiment.

PART 2 — DISPOSITION:
Analyze the conversation to determine the most likely call outcome. Only generate disposition when there is clear evidence in the transcript. Set confidence between 0.0-1.0.

Return JSON object:
{{
  "insights": [
    {{"type": "intent|suggestion|policy|alert|sentiment", "text": "<120 chars", "priority": "high|medium|low", "reasoning": "brief explanation"}}
  ],
  "disposition": {{
    "result": "PTP|Won't Pay|Can't Pay|Wrong Number|Invalid Number|Not Reachable|Not Picking",
    "confidence": 0.0-1.0,
    "date": "YYYY-MM-DD or null",
    "amount": "CHF XX,XXX or null",
    "reason": "reason string or null",
    "notes": "<150 chars summarizing outcome",
    "nextAction": "Follow-up Call|Send Payment Link|Escalate to Supervisor|Legal Notice|No Action",
    "reasoning": "brief explanation of why this disposition was chosen"
  }}
}}

RULES:
- Use ONLY the data provided. NEVER fabricate amounts, dates, or account numbers.
- DO NOT repeat previous insights. Return empty insights array if no new insights warranted.
- For disposition:
  - Only populate "date" and "amount" when result is "PTP" and customer explicitly commits.
  - Only populate "reason" when result is "Won't Pay" or "Can't Pay".
  - Set confidence < 0.5 if conversation is still early/ambiguous — the agent will review.
  - Set confidence >= 0.7 only when the customer has made a clear, unambiguous commitment or refusal.
  - If insufficient conversation data, return disposition as null.
- Keep insight text concise and actionable (under 120 characters).
- Priority HIGH for urgent actions, alerts, or critical information.
- Priority MEDIUM for helpful suggestions or policy reminders.
- Priority LOW for sentiment observations or general context.

LANGUAGE: Generate all insight text and disposition notes in {language_name}. Keep amounts, dates, and account numbers in their original format.

CRITICAL: Return ONLY valid JSON. Do NOT include any explanation, rationale, or additional text before or after the JSON object.
"""
    return prompt


class InsightEngine:
    """
    Insight engine instance for a single call.
    Maintains all state in-memory, triggers LLM calls based on conversation flow.

    v2 mode (COPILOT_V2_ENABLED=true, default):
      - Simplified prompt: next_move + disposition only
      - Streaming Bedrock: pushes next_move early (~800ms)
      - Two-phase HTTP push to /copilot/{callId}/next-move and /copilot/{callId}/disposition
      - Pydantic validation via copilot_schema.py
      - Fires only on meaningful customer turns (>= 10 chars)

    Legacy mode (COPILOT_V2_ENABLED=false):
      - Original combined prompt with insights/warnings
      - Single push to /insight/push-copilot
    """

    def __init__(self, call_sid: str, http_session, mobile_number: str | None = None):
        self.call_sid = call_sid
        self.mobile_number = mobile_number
        self.http_session = http_session
        self.backend_url = os.getenv("BACKEND_URL", "http://localhost:8080")

        # API keys
        self.anthropic_api_key = os.getenv("ANTHROPIC_API_KEY", "")
        self.openai_api_key = os.getenv("OPENAI_API_KEY", "")

        # Vertex AI configuration
        self.gcp_project_id = os.getenv("GCP_PROJECT_ID", "")
        self.gcp_location = os.getenv("GCP_LOCATION", "us-central1")
        self.gemini_model = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")
        self.google_application_credentials = os.getenv(
            "GOOGLE_APPLICATION_CREDENTIALS", ""
        )
        self.google_application_credentials_json = os.getenv(
            "GOOGLE_APPLICATION_CREDENTIALS_JSON", ""
        )

        # AWS Bedrock configuration
        self.aws_region = os.getenv("AWS_REGION", "us-east-1")

        # Cerebras configuration — the model name is the ONLY thing that changes
        # per model swap, and it lives solely in .env (CEREBRAS_MODEL).
        self.cerebras_api_key = os.getenv("CEREBRAS_API_KEY", "")
        self.cerebras_model = os.getenv("CEREBRAS_MODEL", "")
        # Reasoning models (e.g. gpt-oss-120b) have unreliable streaming and need the
        # non-streaming path, reasoning_effort, a larger token budget and json_object
        # output. Everything else (gemma-4-31b, llama, qwen) uses the default streaming
        # path. Derived from the model name so switching models stays a .env-only change.
        _cerebras_reasoning_models = {"gpt-oss-120b"}
        self.cerebras_is_reasoning_model = self.cerebras_model in _cerebras_reasoning_models

        # AI provider selection
        self.ai_provider = os.getenv("AI_PROVIDER", "openai").lower()
        self.copilot_v2 = COPILOT_V2_ENABLED
        print(
            f"[InsightEngine] AI Provider: {self.ai_provider} | Copilot v2: {self.copilot_v2}"
        )

        # In-memory state
        self.transcript: List[Dict] = []
        self.previous_insights: List[Dict] = []
        self.customer_utterance_count = 0
        self.last_customer_sentiment: Optional[str] = None
        self.rate_limit_timestamps: Dict[str, float] = {}
        self.customer_profile: Dict = {}

        # Precooked static system prompt (customer profile + ML + policies + flow),
        # built ONCE per call and reused every turn so the provider serves it from
        # prompt cache ("LLM memory"). Cleared in reset_for_call_end() so the next
        # customer starts with a fresh context. None => not yet precooked.
        self._cached_system_prompt: Optional[str] = None

        # Lock to prevent concurrent LLM calls
        self._llm_lock = asyncio.Lock()

        # Latency tracking for v2 cycle
        self._v2_cycle_start: float = 0.0

        # Conversation summary state
        self._summary_lock = asyncio.Lock()
        self._last_summary_customer_count: int = 0
        self._summary_interval: int = 2  # generate summary every N customer turns
        self._summary_items: List[Dict] = []

        # AI Insights accumulation (Summary-style, displayed in summary section)
        self._ai_insight_lock = asyncio.Lock()
        self._ai_insights: List[Dict] = []
        self._last_ai_insight_customer_count: int = 0
        self._ai_insight_interval: int = (
            2  # generate AI insights every N customer turns
        )

        # AI clients (lazy init)
        self._claude_client = None
        self._openai_client = None
        self._bedrock_client = None
        self._gemini_client = None
        self._cerebras_client = None

    async def initialize(self):
        """Fetch customer profile from backend using mobile number."""
        try:
            url = (
                f"{self.backend_url}/collassistantapi/customer/mobile/{self.mobile_number}/context"
            )
            async with self.http_session.get(url) as resp:
                if resp.status == 200:
                    result = await resp.json()
                    self.customer_profile = result.get("data", {})
                    print(
                        f"[InsightEngine] Customer context loaded for mobile={self.mobile_number}"
                    )
                    # Precook the static customer prompt now (at call start) so the
                    # first mid-call turn doesn't pay the build cost and the provider
                    # can cache it for the whole conversation.
                    if self.customer_profile:
                        self._precook_system_prompt()
                else:
                    print(
                        f"[InsightEngine] Failed to fetch customer context: {resp.status}"
                    )
        except Exception as e:
            print(f"[InsightEngine] Error fetching customer context: {e}")

    def _precook_system_prompt(self) -> str:
        """Build the static, customer-specific system prompt ONCE and cache it for
        the whole call. Every turn reuses the exact same string, so the provider's
        prompt cache serves it instead of reprocessing the customer profile each
        turn — the key latency win. Idempotent: returns the cached value if present.

        Only the static profile is needed here (no transcript), so this is safe to
        run at call start. Cleared by reset_for_call_end()."""
        if self._cached_system_prompt is not None:
            return self._cached_system_prompt

        customer = self.customer_profile.get("customer", {})
        loan = self.customer_profile.get("loan", {})
        additional = self.customer_profile.get("additional", {})
        payment_history = self.customer_profile.get("payment_history", [])
        active_policies = self.customer_profile.get("active_policies", [])

        payment_toon = json_to_toon(payment_history) if payment_history else ""
        policy_lines = [f"-{p.get('policy', '')}:{p.get('rule', '')}" for p in active_policies]
        call_flow_text = format_flow_text(select_flow(self.customer_profile))
        prediction_line = format_prediction(self.customer_profile.get("prediction"))

        # build_copilot_prompt now puts ALL static context into the system prompt and
        # only the transcript into the user prompt, so we can build the system prompt
        # with an empty transcript here and discard the (empty) user prompt.
        system_prompt, _ = self.build_copilot_prompt(
            customer,
            loan,
            additional,
            payment_toon,
            policy_lines,
            0,
            [],
            include_disposition=False,
            include_contextual=True,
            call_flow_text=call_flow_text,
            preferred_language=customer.get("preferredLanguage", "en"),
            prediction_line=prediction_line,
        )
        self._cached_system_prompt = system_prompt
        print(
            f"[CopilotEngine] 🍳 Precooked customer context into cached system prompt "
            f"({len(system_prompt)} chars) for call_sid={self.call_sid}"
        )
        # Dump the FULL precooked system prompt so we can see exactly what static
        # context gets sent to (and cached by) the LLM for this call.
        print(
            "\n"
            "========== PRECOOKED SYSTEM PROMPT ==========\n"
            f"call_sid={self.call_sid} | mobile={self.mobile_number} | chars={len(system_prompt)}\n"
            "---------------------------------------------\n"
            f"{system_prompt}\n"
            "=============================================\n"
        )
        return self._cached_system_prompt

    def reset_for_call_end(self):
        """Clear the precooked context and per-call state so the next customer
        starts fresh (req: clear the LLM 'memory' between calls). The provider's
        own prompt cache is ephemeral and keyed on the prefix, so a new customer
        naturally forms a new cached prefix — this just drops our local handles."""
        self._cached_system_prompt = None
        _system_prompt_hash_per_call.pop(self.call_sid, None)
        self.transcript.clear()
        self.previous_insights.clear()
        print(f"[CopilotEngine] 🧹 Cleared precooked context for call_sid={self.call_sid}")

    async def process_utterance(self, speaker: str, text: str, timestamp: str):
        """
        Main entry point: process a new utterance.
        Classifies sentiment, checks triggers, fires background LLM call if needed.
        """
        sentiment = classify_sentiment(text) if speaker == "customer" else None

        utterance = {
            "speaker": speaker,
            "text": text,
            "time": timestamp,
            "sentiment": sentiment,
        }
        self.transcript.append(utterance)

        if speaker == "customer":
            self.customer_utterance_count += 1
            self.last_customer_sentiment = sentiment

        # Fire copilot only on meaningful customer turns
        if should_fire_copilot(speaker, text):
            if not self._llm_lock.locked():
                trigger_reason = (
                    "first_insight"
                    if len(self.previous_insights) == 0
                    else "continuous_monitoring"
                )
                print(
                    f"[InsightEngine] 🚀 Triggered copilot: {trigger_reason} "
                    f"(customer utterance #{self.customer_utterance_count}, len={len(text.strip())})"
                )
                asyncio.create_task(self._generate_and_push_insights(trigger_reason))
            else:
                print(
                    f"[InsightEngine] ⏸️  LLM call in progress, skipping "
                    f"(customer utterance #{self.customer_utterance_count})"
                )
        elif speaker == "customer":
            print(
                f"[InsightEngine] ⏭️  Skipping short customer utterance (len={len(text.strip())})"
            )

        # Fire periodic combined summary and AI updates every N customer turns
        if speaker == "customer":
            customer_turns_since_last = (
                self.customer_utterance_count - self._last_summary_customer_count
            )
            if customer_turns_since_last >= self._summary_interval:
                if (
                    not self._summary_lock.locked()
                    and not self._ai_insight_lock.locked()
                ):
                    asyncio.create_task(self._generate_and_push_periodic_updates())

    async def _generate_and_push_insights(self, trigger_reason: str):
        """
        Background task: call copilot LLM, parse response, push to backend.
        v2: two-phase push (next_move first, disposition after full parse).
        Legacy: single push to /insight/push-copilot.
        """
        async with self._llm_lock:
            try:
                if self.copilot_v2:
                    await self._generate_and_push_v2(trigger_reason)
                else:
                    await self._generate_and_push_legacy(trigger_reason)
            except Exception as e:
                print(f"[CopilotEngine] Error generating copilot response: {e}")

    # ── v2 path ──────────────────────────────────────────────────────────────

    async def _generate_and_push_v2(self, trigger_reason: str):
        """v2 copilot: simplified prompt, streaming with three-phase push."""
        from copilot_schema import parse_llm_response, normalize_priority

        prompt_start = time.time()
        self._v2_cycle_start = prompt_start

        # Disposition is now generated at call-end by the Java backend, not during the call
        include_disposition = False
        include_contextual = True

        # Static customer context: precooked ONCE per call (in initialize, or lazily
        # here on the first turn) and reused verbatim every turn so the provider
        # serves it from prompt cache instead of reprocessing it mid-conversation.
        system_prompt = self._precook_system_prompt()

        # Only the live transcript changes per turn → rebuild just the user prompt.
        transcript_lines = preprocess_transcript(self.transcript, MAX_TRANSCRIPT_TURNS)
        recent_count = min(len(self.transcript), MAX_TRANSCRIPT_TURNS)
        user_prompt = self.build_user_prompt(transcript_lines, recent_count)

        # (A1) Cache Consistency
        verify_cache_consistency(self.call_sid, system_prompt)

        prompt_time = (time.time() - prompt_start) * 1000
        print(
            f"[CopilotEngine] 📝 v2 prompt built in {prompt_time:.0f}ms"
        )

        # Dump the full prompt that will be sent to the LLM (for debugging).
        print(
            "\n"
            "========== LLM REQUEST (v2) ==========\n"
            f"provider={self.ai_provider} | trigger={trigger_reason} | "
            f"include_disposition={include_disposition} | include_contextual={include_contextual}\n"
            "---------- SYSTEM PROMPT ----------\n"
            f"{system_prompt}\n"
            "---------- USER PROMPT ----------\n"
            f"{user_prompt}\n"
            "======================================\n"
        )

        llm_start = time.time()
        print(
            f"[CopilotEngine] 🔄 Calling {self.ai_provider.upper()} (v2 streaming) for {trigger_reason}..."
        )

        max_tokens = 450

        # All providers stream with early next_move + contextual_details push callbacks
        if self.ai_provider == "cerebras":
            accumulated = await self._call_cerebras_api_streaming(
                system_prompt,
                user_prompt,
                on_next_move_ready=self._push_next_move,
                on_contextual_details_ready=self._push_contextual_details,
                # max_tokens=max_tokens,
            )
        elif self.ai_provider == "bedrock":
            accumulated = await self._call_bedrock_api_streaming(
                system_prompt,
                user_prompt,
                on_next_move_ready=self._push_next_move,
                on_contextual_details_ready=self._push_contextual_details,
                max_tokens=max_tokens,
            )
        elif self.ai_provider == "openai":
            accumulated = await self._call_openai_api_v2_streaming(
                system_prompt,
                user_prompt,
                on_next_move_ready=self._push_next_move,
                on_contextual_details_ready=self._push_contextual_details,
                # max_tokens=max_tokens,
            )
        elif self.ai_provider == "gemini":
            # Gemini: no streaming support yet — fallback to sequential push
            accumulated = await self._call_gemini_api_v2(
                system_prompt, user_prompt
            )
            from copilot_schema import extract_next_move, extract_contextual_details

            next_move_dict = extract_next_move(accumulated)
            if next_move_dict:
                await self._push_next_move(next_move_dict)

            contextual_details_dict = extract_contextual_details(accumulated)
            if contextual_details_dict:
                await self._push_contextual_details(contextual_details_dict)
        else:  # claude (default)
            accumulated = await self._call_claude_api_v2_streaming(
                system_prompt,
                user_prompt,
                on_next_move_ready=self._push_next_move,
                on_contextual_details_ready=self._push_contextual_details,
                max_tokens=max_tokens,
            )

        llm_latency = (time.time() - llm_start) * 1000
        print(
            f"[CopilotEngine] ⚡ {self.ai_provider.upper()} responded in {llm_latency:.0f}ms"
        )

        # Validate full response with Pydantic
        parse_start = time.time()
        if not accumulated or not accumulated.strip():
            print("[CopilotEngine] ❌ Skipping parse — empty response from LLM")
            return
        try:
            parsed = parse_llm_response(accumulated)
        except Exception as e:
            print(
                f"[CopilotEngine] ❌ Pydantic validation failed: {e} | raw: {accumulated[:300]}"
            )
            return

        # 🔥 PUSH INSIGHTS TO BACKEND
        if parsed and getattr(parsed, "insights", None):
            try:
                insights_payload = [
                    {
                        "type": ins.type,
                        "text": ins.text,
                        # Backend standard is high|medium|low — normalize "mid" etc.
                        "priority": normalize_priority(ins.priority)
                    }
                    for ins in parsed.insights
                ]

                payload = {
                    "callSid": self.call_sid,
                    "mobileNumber": self.mobile_number,
                    "items": insights_payload
                }

                # Backend context-path is /collassistantapi (matches the next-move /
                # contextual-details pushes above). The old /uwapi path 404'd.
                url = f"{self.backend_url}/collassistantapi/insight/push"

                async with self.http_session.post(url, json=payload) as resp:
                    print(f"[CopilotEngine] 🚀 Insights push status: {resp.status} | count={len(insights_payload)}")

            except Exception as e:
                print(f"[CopilotEngine] ❌ Error pushing insights: {e}")

        parse_time = (time.time() - parse_start) * 1000
        llm_latency = (time.time() - llm_start) * 1000

        total_time = (time.time() - prompt_start) * 1000
        print(
            f"[CopilotEngine] 🎯 v2 CYCLE COMPLETE in {total_time:.0f}ms "
            f"(prompt: {prompt_time:.0f}ms, LLM: {llm_latency:.0f}ms, parse: {parse_time:.0f}ms)"
        )

    # ── Two-phase push helpers ────────────────────────────────────────────────

    async def _push_next_move(self, next_move_data: dict):
        """Phase 1: POST next_move to /collassistantapi/copilot/{callSid}/next-move."""
        push_start = time.time()
        try:
            payload = {
                "callSid": self.call_sid,
                "mobileNumber": self.mobile_number,
                "points": next_move_data.get("points", []),
                "priority": next_move_data.get("priority", "medium"),
            }
            url = f"{self.backend_url}/collassistantapi/copilot/{self.call_sid}/next-move"
            async with self.http_session.post(url, json=payload) as resp:
                push_latency = (time.time() - push_start) * 1000
                e2e_latency = (
                    (time.time() - self._v2_cycle_start) * 1000
                    if self._v2_cycle_start
                    else 0
                )
                if resp.status == 200:
                    points_str = " | ".join(next_move_data.get("points", []))
                    print(
                        f"[CopilotEngine] ✅ Phase 1: next_move pushed | "
                        f"e2e={e2e_latency:.0f}ms push={push_latency:.0f}ms | "
                        f"points={points_str[:80]} | "
                        f"priority={next_move_data.get('priority', '')}"
                    )
                else:
                    text = await resp.text()
                    print(
                        f"[CopilotEngine] ⚠️  next_move push failed: {resp.status} - {text} (push={push_latency:.0f}ms)"
                    )
        except Exception as e:
            print(f"[CopilotEngine] Error pushing next_move: {e}")

    async def _push_contextual_details(self, contextual_details_data: dict):
        """Phase 1.5: POST contextual_details to /collassistantapi/copilot/{callSid}/contextual-details."""
        push_start = time.time()
        try:
            payload = {
                "callSid": self.call_sid,
                "mobileNumber": self.mobile_number,
                "details": contextual_details_data.get("details", []),
            }
            url = f"{self.backend_url}/collassistantapi/copilot/{self.call_sid}/contextual-details"
            async with self.http_session.post(url, json=payload) as resp:
                push_latency = (time.time() - push_start) * 1000
                e2e_latency = (
                    (time.time() - self._v2_cycle_start) * 1000
                    if self._v2_cycle_start
                    else 0
                )
                if resp.status == 200:
                    detail_count = len(contextual_details_data.get("details", []))
                    print(
                        f"[CopilotEngine] ✅ Phase 1.5: contextual_details pushed | "
                        f"e2e={e2e_latency:.0f}ms push={push_latency:.0f}ms | "
                        f"details={detail_count} items"
                    )
                else:
                    text = await resp.text()
                    print(
                        f"[CopilotEngine] ⚠️  contextual_details push failed: {resp.status} - {text} (push={push_latency:.0f}ms)"
                    )
        except Exception as e:
            print(f"[CopilotEngine] Error pushing contextual_details: {e}")

    # ── Streaming Cerebras ─────────────────────────────────────────────────────

    async def _call_cerebras_api_streaming(
        self,
        system_prompt: str,
        user_prompt: str,
        on_next_move_ready: Callable | None = None,
        on_contextual_details_ready: Callable | None = None,
    ) -> str:
        """
        Stream Cerebras response with three-phase progressive push.
        Uses AsyncCerebras with stream=True (OpenAI-compatible API).
        """
        from copilot_schema import (
            is_next_move_complete,
            extract_next_move,
            is_contextual_details_complete,
            extract_contextual_details,
        )

        if not self.cerebras_api_key:
            print("[InsightEngine] No CEREBRAS_API_KEY, returning mock v2 response")
            mock = '{"next_move":{"points":["Confirm customer identity","Reference loan account"],"priority":"high"},"contextual_details":{"details":[{"label":"Test","value":"Mock","highlight":false}]},"disposition":null}'
            if on_next_move_ready:
                nm = extract_next_move(mock)
                if nm:
                    await on_next_move_ready(nm)
            if on_contextual_details_ready:
                cd = extract_contextual_details(mock)
                if cd:
                    await on_contextual_details_ready(cd)
            return mock

        # Reasoning models have inconsistent streaming behaviour — use non-streaming path directly
        if self.cerebras_is_reasoning_model:
            print(f"[CopilotEngine] ⚡ {self.cerebras_model} → non-streaming (streaming unreliable for this model)")
            accumulated = await self._call_cerebras_api_v2(system_prompt, user_prompt)
            if not accumulated:
                print("[CopilotEngine] ❌ Empty response from Cerebras non-streaming, aborting")
                return ""
            nm_dict = extract_next_move(accumulated)
            if nm_dict and on_next_move_ready:
                await on_next_move_ready(nm_dict)
            cd_dict = extract_contextual_details(accumulated)
            if cd_dict and on_contextual_details_ready:
                await on_contextual_details_ready(cd_dict)
            return accumulated

        try:
            if self._cerebras_client is None:
                from cerebras.cloud.sdk import AsyncCerebras

                self._cerebras_client = AsyncCerebras(api_key=self.cerebras_api_key)

            t_start = time.perf_counter()
            accumulated = ""
            nm_fired = False
            cd_fired = False
            t_first_token = None
            t_next_move_complete = None
            t_contextual_details_complete = None
            token_count = 0

            # Note: response_format is intentionally omitted for stream=True —
            # Cerebras returns content-type:application/json (non-SSE) when both
            # are set together, causing the SDK to yield zero chunks.
            stream = await self._cerebras_client.chat.completions.create(
                model=self.cerebras_model,
                max_tokens=450,
                temperature=0.3,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                stream=True,
                # (Cerebras Rule #2) Pin every turn of THIS call to the same prompt cache so
                # they hit the same backend/DC and reuse the cached static system prefix.
                # Per-conversation key (call_sid) — NOT a key shared across customers.
                # Sent via extra_body since SDK 1.67.0 has no typed prompt_cache_key param.
                extra_body={"prompt_cache_key": f"copilot-{self.call_sid}"},
            )

            async for chunk in stream:
                delta = chunk.choices[0].delta.content if chunk.choices else None
                print(f"[CopilotEngine] 🔹 chunk | delta={repr(delta)}")
                if delta:
                    if t_first_token is None:
                        t_first_token = time.perf_counter()

                    accumulated += delta
                    token_count += 1

                    # Phase 1: next_move
                    if not nm_fired and is_next_move_complete(accumulated):
                        t_next_move_complete = time.perf_counter()
                        nm_dict = extract_next_move(accumulated)
                        if nm_dict and on_next_move_ready:
                            nm_fired = True
                            await on_next_move_ready(nm_dict)
                        elif not nm_dict:
                            print(
                                f"[CopilotEngine] ⚠️ extract_next_move returned None | accumulated so far: {accumulated[:500]}"
                            )

                    # Phase 1.5: contextual_details
                    if not cd_fired and is_contextual_details_complete(accumulated):
                        t_contextual_details_complete = time.perf_counter()
                        cd_dict = extract_contextual_details(accumulated)
                        if cd_dict and on_contextual_details_ready:
                            cd_fired = True
                            await on_contextual_details_ready(cd_dict)
                        elif not cd_dict:
                            print(
                                f"[CopilotEngine] ⚠️ extract_contextual_details returned None | accumulated so far: {accumulated[:500]}"
                            )

            t_end = time.perf_counter()

            # Fallback: if stream yielded nothing, retry as non-streaming
            if not accumulated:
                print("[CopilotEngine] ⚠️ Stream returned empty — falling back to non-streaming Cerebras call")
                response = await self._cerebras_client.chat.completions.create(
                    model=self.cerebras_model,
                    max_tokens=450,
                    temperature=0.3,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                    response_format=_CEREBRAS_RESPONSE_FORMAT,
                )
                accumulated = response.choices[0].message.content or ""
                print(f"[CopilotEngine] 🔁 Fallback response ({len(accumulated)} chars): {accumulated[:200]}")
                # Fire callbacks from the complete response
                if accumulated:
                    nm_dict = extract_next_move(accumulated)
                    if nm_dict and on_next_move_ready and not nm_fired:
                        await on_next_move_ready(nm_dict)
                    cd_dict = extract_contextual_details(accumulated)
                    if cd_dict and on_contextual_details_ready and not cd_fired:
                        await on_contextual_details_ready(cd_dict)

            # Latency breakdown
            input_token_estimate = len((system_prompt + user_prompt).split()) * 1.3
            print(
                f"[CopilotEngine] CEREBRAS TIMING"
                f" | input_tokens≈{int(input_token_estimate)}"
                f" | output_tokens≈{token_count}"
                f" | ttft={int((t_first_token - t_start) * 1000) if t_first_token else 'N/A'}ms"
                f" | next_move_ready={int((t_next_move_complete - t_start) * 1000) if t_next_move_complete else 'N/A'}ms"
                f" | contextual_details_ready={int((t_contextual_details_complete - t_start) * 1000) if t_contextual_details_complete else 'N/A'}ms"
                f" | e2e={int((t_end - t_start) * 1000)}ms"
                f" | generation={int((t_end - t_first_token) * 1000) if t_first_token else 'N/A'}ms"
            )

            return accumulated
        except Exception as e:
            print(f"[InsightEngine] Cerebras streaming error: {e}")
            return ""

    # ── Streaming Bedrock ─────────────────────────────────────────────────────

    async def _call_bedrock_api_streaming(
        self,
        system_prompt: str,
        user_prompt: str,
        on_next_move_ready: Callable | None = None,
        on_contextual_details_ready: Callable | None = None,
        max_tokens: int = 450,
    ) -> str:
        """
        Stream Bedrock response.
        Three-phase progressive push:
        1. next_move JSON object complete → fire on_next_move_ready
        2. contextual_details JSON object complete → fire on_contextual_details_ready
        3. Full response complete → return accumulated text
        """
        loop = asyncio.get_event_loop()
        next_move_pushed = {"done": False}
        contextual_details_pushed = {"done": False}

        async def fire_next_move(nm_dict: dict):
            if not next_move_pushed["done"] and on_next_move_ready:
                next_move_pushed["done"] = True
                await on_next_move_ready(nm_dict)

        async def fire_contextual_details(cd_dict: dict):
            if not contextual_details_pushed["done"] and on_contextual_details_ready:
                contextual_details_pushed["done"] = True
                await on_contextual_details_ready(cd_dict)

        def sync_stream() -> str:
            """Synchronous Bedrock streaming — runs in a thread executor."""
            from copilot_schema import (
                is_next_move_complete,
                extract_next_move,
                is_contextual_details_complete,
                extract_contextual_details,
            )

            t_start = time.perf_counter()

            if self._bedrock_client is None:
                import boto3
                from botocore.config import Config

                self._bedrock_client = boto3.client(
                    "bedrock-runtime",
                    region_name=self.aws_region,
                    config=Config(
                        retries={"max_attempts": 2, "mode": "adaptive"},
                        read_timeout=10,
                        connect_timeout=5,
                    ),
                )

            model_id = "arn:aws:bedrock:ap-south-1:144918211563:inference-profile/global.anthropic.claude-haiku-4-5-20251001-v1:0"
            # model_id = "arn:aws:bedrock:ap-south-1:144918211563:inference-profile/global.anthropic.claude-sonnet-4-6"

            body = json.dumps(
                {
                    "anthropic_version": "bedrock-2023-05-31",
                    "max_tokens": max_tokens,
                    "system": system_prompt,
                    "messages": [{"role": "user", "content": user_prompt}],
                    "temperature": 0.3,
                }
            )

            response = self._bedrock_client.invoke_model_with_response_stream(
                modelId=model_id,
                body=body,
                contentType="application/json",
            )

            t_first_token = None
            t_next_move_complete = None
            t_contextual_details_complete = None
            accumulated = ""
            nm_fired = False
            cd_fired = False
            token_count = 0

            for event in response["body"]:
                chunk = json.loads(event["chunk"]["bytes"])
                if chunk.get("type") == "content_block_delta":
                    if t_first_token is None:
                        t_first_token = time.perf_counter()

                    delta_text = chunk.get("delta", {}).get("text", "")
                    accumulated += delta_text
                    token_count += 1

                    # Phase 1: Check for next_move completion
                    if not nm_fired and is_next_move_complete(accumulated):
                        t_next_move_complete = time.perf_counter()
                        nm_dict = extract_next_move(accumulated)
                        if nm_dict:
                            nm_fired = True
                            asyncio.run_coroutine_threadsafe(
                                fire_next_move(nm_dict), loop
                            )
                        else:
                            print(
                                f"[CopilotEngine] ⚠️ extract_next_move returned None | accumulated so far: {accumulated[:500]}"
                            )

                    # Phase 1.5: Check for contextual_details completion
                    if not cd_fired and is_contextual_details_complete(accumulated):
                        t_contextual_details_complete = time.perf_counter()
                        cd_dict = extract_contextual_details(accumulated)
                        if cd_dict:
                            cd_fired = True
                            asyncio.run_coroutine_threadsafe(
                                fire_contextual_details(cd_dict), loop
                            )
                        else:
                            print(
                                f"[CopilotEngine] ⚠️ extract_contextual_details returned None | accumulated so far: {accumulated[:500]}"
                            )

            t_end = time.perf_counter()

            # Latency breakdown
            input_token_estimate = len((system_prompt + user_prompt).split()) * 1.3
            print(
                f"[CopilotEngine] TIMING BREAKDOWN"
                f" | input_tokens≈{int(input_token_estimate)}"
                f" | output_tokens≈{token_count}"
                f" | ttft={int((t_first_token - t_start) * 1000) if t_first_token else 'N/A'}ms"
                f" | next_move_ready={int((t_next_move_complete - t_start) * 1000) if t_next_move_complete else 'N/A'}ms"
                f" | contextual_details_ready={int((t_contextual_details_complete - t_start) * 1000) if t_contextual_details_complete else 'N/A'}ms"
                f" | e2e={int((t_end - t_start) * 1000)}ms"
                f" | generation={int((t_end - t_first_token) * 1000) if t_first_token else 'N/A'}ms"
            )

            return accumulated

        try:
            accumulated = await loop.run_in_executor(None, sync_stream)
            return accumulated
        except Exception as e:
            print(f"[InsightEngine] Bedrock streaming error: {e}")
            return ""

    # ── Streaming Claude ───────────────────────────────────────────────────

    async def _call_claude_api_v2_streaming(
        self,
        system_prompt: str,
        user_prompt: str,
        on_next_move_ready: Callable | None = None,
        on_contextual_details_ready: Callable | None = None,
    ) -> str:
        """Stream Claude response with three-phase progressive push."""
        from copilot_schema import (
            is_next_move_complete,
            extract_next_move,
            is_contextual_details_complete,
            extract_contextual_details,
        )

        if not self.anthropic_api_key:
            print("[InsightEngine] No ANTHROPIC_API_KEY, returning mock v2 response")
            mock = '{"next_move":{"points":["Confirm customer identity","Reference loan account"],"priority":"high"},"contextual_details":{"details":[{"label":"Test","value":"Mock","highlight":false}]},"disposition":null}'
            if on_next_move_ready:
                nm = extract_next_move(mock)
                if nm:
                    await on_next_move_ready(nm)
            if on_contextual_details_ready:
                cd = extract_contextual_details(mock)
                if cd:
                    await on_contextual_details_ready(cd)
            return mock

        try:
            if self._claude_client is None:
                from anthropic import AsyncAnthropic

                self._claude_client = AsyncAnthropic(api_key=self.anthropic_api_key)

            accumulated = ""
            nm_fired = False
            cd_fired = False

            async with self._claude_client.messages.stream(
                model="claude-sonnet-4-5-20250929",
                max_tokens=450,
                temperature=0.3,
                system=[
                    {
                        "type": "text",
                        "text": system_prompt,
                        "cache_control": {"type": "ephemeral"},
                    }
                ],
                messages=[{"role": "user", "content": user_prompt}],
            ) as stream:
                async for text in stream.text_stream:
                    accumulated += text

                    # Phase 1: next_move
                    if not nm_fired and is_next_move_complete(accumulated):
                        nm_dict = extract_next_move(accumulated)
                        if nm_dict and on_next_move_ready:
                            nm_fired = True
                            await on_next_move_ready(nm_dict)
                        elif not nm_dict:
                            print(
                                f"[CopilotEngine] ⚠️ extract_next_move returned None | accumulated so far: {accumulated[:500]}"
                            )

                    # Phase 1.5: contextual_details
                    if not cd_fired and is_contextual_details_complete(accumulated):
                        cd_dict = extract_contextual_details(accumulated)
                        if cd_dict and on_contextual_details_ready:
                            cd_fired = True
                            await on_contextual_details_ready(cd_dict)
                        elif not cd_dict:
                            print(
                                f"[CopilotEngine] ⚠️ extract_contextual_details returned None | accumulated so far: {accumulated[:500]}"
                            )

            return accumulated
        except Exception as e:
            print(f"[InsightEngine] Claude v2 streaming error: {e}")
            return ""

    # ── Streaming OpenAI ─────────────────────────────────────────────────

    async def _call_openai_api_v2_streaming(
        self,
        system_prompt: str,
        user_prompt: str,
        on_next_move_ready: Callable | None = None,
        on_contextual_details_ready: Callable | None = None,
    ) -> str:
        """Stream OpenAI response with three-phase progressive push."""
        from copilot_schema import (
            is_next_move_complete,
            extract_next_move,
            is_contextual_details_complete,
            extract_contextual_details,
        )

        if not self.openai_api_key:
            print("[InsightEngine] No OPENAI_API_KEY, returning mock v2 response")
            mock = '{"next_move":{"points":["Confirm customer identity","Reference loan account"],"priority":"high"},"contextual_details":{"details":[{"label":"Test","value":"Mock","highlight":false}]},"disposition":null}'
            if on_next_move_ready:
                nm = extract_next_move(mock)
                if nm:
                    await on_next_move_ready(nm)
            if on_contextual_details_ready:
                cd = extract_contextual_details(mock)
                if cd:
                    await on_contextual_details_ready(cd)
            return mock

        try:
            if self._openai_client is None:
                from openai import AsyncOpenAI

                self._openai_client = AsyncOpenAI(api_key=self.openai_api_key)

            accumulated = ""
            nm_fired = False
            cd_fired = False

            stream = await self._openai_client.chat.completions.create(
                model="gpt-5-nano-2025-08-07",
                max_tokens=450,
                temperature=0.3,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                stream=True,
            )

            async for chunk in stream:
                delta = chunk.choices[0].delta.content
                if delta:
                    accumulated += delta

                    # Phase 1: next_move
                    if not nm_fired and is_next_move_complete(accumulated):
                        nm_dict = extract_next_move(accumulated)
                        if nm_dict and on_next_move_ready:
                            nm_fired = True
                            await on_next_move_ready(nm_dict)
                        elif not nm_dict:
                            print(
                                f"[CopilotEngine] ⚠️ extract_next_move returned None | accumulated so far: {accumulated[:500]}"
                            )

                    # Phase 1.5: contextual_details
                    if not cd_fired and is_contextual_details_complete(accumulated):
                        cd_dict = extract_contextual_details(accumulated)
                        if cd_dict and on_contextual_details_ready:
                            cd_fired = True
                            await on_contextual_details_ready(cd_dict)
                        elif not cd_dict:
                            print(
                                f"[CopilotEngine] ⚠️ extract_contextual_details returned None | accumulated so far: {accumulated[:500]}"
                            )

            return accumulated
        except Exception as e:
            print(f"[InsightEngine] OpenAI v2 streaming error: {e}")
            return ""

    # ── v2 LLM callers (non-streaming fallback) ──────────────────────────

    async def _call_claude_api_v2(self, system_prompt: str, user_prompt: str) -> str:
        """Call Claude with separate system/user prompts (v2 schema, prompt caching)."""
        if not self.anthropic_api_key:
            print("[InsightEngine] No ANTHROPIC_API_KEY, returning mock v2 response")
            return '{"next_move":{"points":["Confirm customer identity","Reference loan account"],"priority":"high"},"disposition":null}'

        try:
            if self._claude_client is None:
                from anthropic import AsyncAnthropic

                self._claude_client = AsyncAnthropic(api_key=self.anthropic_api_key)

            response = await self._claude_client.messages.create(
                model="claude-sonnet-4-5-20250929",
                max_tokens=450,
                temperature=0.3,
                system=[
                    {
                        "type": "text",
                        "text": system_prompt,
                        "cache_control": {"type": "ephemeral"},
                    }
                ],
                messages=[{"role": "user", "content": user_prompt}],
            )
            return response.content[0].text
        except Exception as e:
            print(f"[InsightEngine] Claude v2 API error: {e}")
            return ""

    async def _call_openai_api_v2(self, system_prompt: str, user_prompt: str) -> str:
        """Call OpenAI with separate system/user prompts (v2 schema)."""
        if not self.openai_api_key:
            print("[InsightEngine] No OPENAI_API_KEY, returning mock v2 response")
            return '{"next_move":{"points":["Confirm customer identity","Reference loan account"],"priority":"high"},"disposition":null}'

        try:
            if self._openai_client is None:
                from openai import AsyncOpenAI

                self._openai_client = AsyncOpenAI(api_key=self.openai_api_key)

            response = await self._openai_client.chat.completions.create(
                model="gpt-5-nano-2025-08-07",
                max_tokens=450,
                temperature=0.3,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
            )
            return response.choices[0].message.content
        except Exception as e:
            print(f"[InsightEngine] OpenAI v2 API error: {e}")
            return ""

    async def _call_gemini_api_v2(self, system_prompt: str, user_prompt: str) -> str:
        """Call Gemini with combined prompt (v2 schema)."""
        if not self.gcp_project_id:
            print("[InsightEngine] No GCP_PROJECT_ID, returning mock v2 response")
            return '{"next_move":{"points":["Confirm customer identity","Reference loan account"],"priority":"high"},"disposition":null}'

        try:
            if self._gemini_client is None:
                from vertexai.generative_models import GenerativeModel
                import vertexai
                from google.oauth2 import service_account

                credentials = None
                if self.google_application_credentials_json:
                    import json as json_module

                    creds_dict = json_module.loads(
                        self.google_application_credentials_json
                    )
                    credentials = service_account.Credentials.from_service_account_info(
                        creds_dict
                    )
                elif self.google_application_credentials:
                    credentials = service_account.Credentials.from_service_account_file(
                        self.google_application_credentials
                    )

                vertexai.init(
                    project=self.gcp_project_id,
                    location=self.gcp_location,
                    credentials=credentials,
                )
                self._gemini_client = GenerativeModel(self.gemini_model)

            combined = f"{system_prompt}\n\n{user_prompt}"
            response = await self._gemini_client.generate_content_async(
                contents=combined,
                generation_config={"temperature": 0.3, "max_output_tokens": 450},
            )
            return response.text
        except Exception as e:
            print(f"[InsightEngine] Gemini v2 API error: {e}")
            return ""

    @staticmethod
    def _log_prompt_cache_usage(response, label: str):
        """Print prompt-token cache stats so prompt caching is observable in the logs.

        OpenAI-compatible providers (incl. Cerebras) return
        usage.prompt_tokens_details.cached_tokens = the number of prompt-prefix tokens
        served from cache. cached_tokens ≈ 0 on the first turn of a call and jumps to
        roughly the system-prompt size on subsequent turns — proof the precooked static
        prompt is being reused from the provider's cache rather than reprocessed."""
        try:
            usage = getattr(response, "usage", None)
            if not usage:
                print(f"[CopilotEngine] 🧠 prompt cache [{label}]: no usage on response")
                return
            prompt = getattr(usage, "prompt_tokens", None)
            completion = getattr(usage, "completion_tokens", None)
            details = getattr(usage, "prompt_tokens_details", None)
            cached = getattr(details, "cached_tokens", None) if details is not None else None
            if cached is None and isinstance(details, dict):
                cached = details.get("cached_tokens")
            pct = f"{round(100 * cached / prompt)}%" if cached and prompt else "0%"
            print(
                f"[CopilotEngine] 🧠 prompt cache [{label}]: prompt_tokens={prompt} "
                f"cached_tokens={cached if cached is not None else 'n/a'} ({pct} of prompt) "
                f"completion_tokens={completion}"
            )
        except Exception as e:
            print(f"[CopilotEngine] (prompt cache usage log failed: {e})")

    async def _call_cerebras_api_v2(self, system_prompt: str, user_prompt: str) -> str:
        """Call Cerebras non-streaming (safe extraction for reasoning models and fallback path)."""
        if not self.cerebras_api_key:
            print("[InsightEngine] No CEREBRAS_API_KEY, returning mock v2 response")
            return '{"next_move":{"points":["Confirm customer identity","Reference loan account"],"priority":"high"},"disposition":null}'

        try:
            if self._cerebras_client is None:
                from cerebras.cloud.sdk import AsyncCerebras

                self._cerebras_client = AsyncCerebras(api_key=self.cerebras_api_key)

            is_reasoning_model = self.cerebras_is_reasoning_model

            extra_kwargs = {}
            if is_reasoning_model:
                extra_kwargs["reasoning_effort"] = "low"

            response = await self._cerebras_client.chat.completions.create(
                model=self.cerebras_model,
                max_tokens=4096 if is_reasoning_model else 450,
                temperature=0.3,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                stream=False,
                response_format={"type": "json_object"} if is_reasoning_model else _CEREBRAS_RESPONSE_FORMAT,
                # (Cerebras Rule #2) Per-conversation prompt cache key so all turns of this
                # call route to the same backend and reuse the cached static system prefix.
                # Sent via extra_body since SDK 1.67.0 has no typed prompt_cache_key param.
                extra_body={"prompt_cache_key": f"copilot-{self.call_sid}"},
                **extra_kwargs,
            )

            if not response or not response.choices:
                print("[CopilotEngine] ❌ Empty response from Cerebras (no choices)")
                return ""

            # Prompt-cache visibility: shows how many prompt (prefix) tokens the provider
            # served from cache. ~0 on the first turn of a call, then jumps to ≈ the static
            # system-prompt size on later turns — that jump IS the precooked prompt being
            # reused from "LLM memory" instead of reprocessed.
            self._log_prompt_cache_usage(response, "cerebras non-streaming")

            choice = response.choices[0]
            if hasattr(choice, "message") and choice.message:
                return choice.message.content or ""
            elif hasattr(choice, "text"):
                return choice.text or ""
            else:
                print("[CopilotEngine] ❌ Unknown Cerebras response format")
                return ""

        except Exception as e:
            print(f"[CopilotEngine] ❌ Cerebras non-streaming error: {e}")
            return ""

    # ── Legacy path ───────────────────────────────────────────────────────────

    async def _generate_and_push_legacy(self, trigger_reason: str):
        """Legacy copilot flow: single combined prompt, push to /insight/push-copilot."""
        prompt_start = time.time()

        prompt = build_llm_prompt(
            self.customer_profile,
            self.transcript,
            self.previous_insights,
        )
        prompt_time = (time.time() - prompt_start) * 1000
        print(f"[CopilotEngine] 📝 Legacy prompt built in {prompt_time:.0f}ms")

        # Dump the full prompt that will be sent to the LLM (for debugging).
        print(
            "\n"
            "========== LLM REQUEST (legacy) ==========\n"
            f"provider={self.ai_provider} | trigger={trigger_reason}\n"
            "---------- PROMPT ----------\n"
            f"{prompt}\n"
            "==========================================\n"
        )

        llm_start = time.time()
        print(
            f"[CopilotEngine] 🔄 Calling {self.ai_provider.upper()} (legacy) for {trigger_reason}..."
        )

        if self.ai_provider == "cerebras":
            response_text = await self._call_cerebras_api(prompt)
        elif self.ai_provider == "openai":
            response_text = await self._call_openai_api(prompt)
        elif self.ai_provider == "bedrock":
            response_text = await self._call_bedrock_api(prompt)
        elif self.ai_provider == "gemini":
            response_text = await self._call_gemini_api(prompt)
        else:
            response_text = await self._call_claude_api(prompt)

        llm_latency = (time.time() - llm_start) * 1000
        print(
            f"[CopilotEngine] ⚡ {self.ai_provider.upper()} responded in {llm_latency:.0f}ms"
        )

        parse_start = time.time()
        copilot_data = parse_copilot_response(response_text)
        parse_time = (time.time() - parse_start) * 1000

        if not copilot_data:
            print("[CopilotEngine] ❌ Failed to parse legacy copilot response")
            return

        push_start = time.time()
        await self._push_copilot_response_legacy(copilot_data)
        push_time = (time.time() - push_start) * 1000

        # Store insights for context
        time_str = datetime.now().strftime("%H:%M:%S")
        for insight in copilot_data.get("insights", []):
            self.previous_insights.append(
                {
                    "type": insight.get("type", ""),
                    "text": insight.get("text", ""),
                    "priority": insight.get("priority", "medium"),
                    "time": time_str,
                }
            )

        total_time = (time.time() - prompt_start) * 1000
        print(f"[CopilotEngine] 🎯 Legacy CYCLE COMPLETE in {total_time:.0f}ms")

    async def _push_copilot_response_legacy(self, copilot_data: Dict):
        """Legacy single-push to /insight/push-copilot."""
        try:
            copilot_data = self._truncate_copilot_response(copilot_data)
            payload = {
                "callSid": self.call_sid,
                "mobile_number": self.mobile_number,
                "next_move": copilot_data["next_move"],
                "warnings": copilot_data.get("warnings", []),
                "insights": copilot_data.get("insights", []),
                "disposition": copilot_data.get("disposition"),
            }
            url = f"{self.backend_url}/collassistantapi/insight/push-copilot"
            async with self.http_session.post(url, json=payload) as resp:
                if resp.status == 200:
                    nm = copilot_data["next_move"]
                    points_str = " | ".join(nm.get("points", []))
                    print(f"[CopilotEngine] ✅ Legacy pushed: points={points_str[:80]}")
                else:
                    text = await resp.text()
                    print(f"[CopilotEngine] Legacy push failed: {resp.status} - {text}")
        except Exception as e:
            print(f"[CopilotEngine] Error pushing legacy response: {e}")

    # ── Legacy LLM callers ────────────────────────────────────────────────────

    async def _call_openai_api(self, prompt: str) -> str:
        if not self.openai_api_key:
            return json.dumps(
                [
                    {
                        "type": "suggestion",
                        "text": "Consider offering a restructured payment plan",
                        "priority": "high",
                        "reasoning": "mock",
                    }
                ]
            )
        try:
            if self._openai_client is None:
                from openai import AsyncOpenAI

                self._openai_client = AsyncOpenAI(api_key=self.openai_api_key)
            response = await self._openai_client.chat.completions.create(
                model="gpt-5-nano-2025-08-07",
                max_tokens=600,
                temperature=0.7,
                messages=[
                    {"role": "system", "content": prompt},
                    {
                        "role": "user",
                        "content": "Generate insights for this conversation.",
                    },
                ],
            )
            return response.choices[0].message.content
        except Exception as e:
            print(f"[InsightEngine] Error calling OpenAI API: {e}")
            return "[]"

    async def _call_cerebras_api(self, prompt: str) -> str:
        """Legacy Cerebras call."""
        if not self.cerebras_api_key:
            return json.dumps(
                [
                    {
                        "type": "suggestion",
                        "text": "Consider offering a restructured payment plan",
                        "priority": "high",
                        "reasoning": "mock",
                    }
                ]
            )
        try:
            if self._cerebras_client is None:
                from cerebras.cloud.sdk import AsyncCerebras

                self._cerebras_client = AsyncCerebras(api_key=self.cerebras_api_key)
            response = await self._cerebras_client.chat.completions.create(
                model=self.cerebras_model,
                max_tokens=600,
                temperature=0.3,
                messages=[
                    {"role": "system", "content": prompt},
                    {
                        "role": "user",
                        "content": "Generate insights for this conversation.",
                    },
                ],
            )
            return response.choices[0].message.content
        except Exception as e:
            print(f"[InsightEngine] Error calling Cerebras API: {e}")
            return "[]"

    async def _call_claude_api(self, prompt: str) -> str:
        if not self.anthropic_api_key:
            return json.dumps(
                [
                    {
                        "type": "suggestion",
                        "text": "Consider offering a restructured payment plan",
                        "priority": "high",
                        "reasoning": "mock",
                    }
                ]
            )
        try:
            if self._claude_client is None:
                from anthropic import AsyncAnthropic

                self._claude_client = AsyncAnthropic(api_key=self.anthropic_api_key)
            response = await self._claude_client.messages.create(
                model="claude-sonnet-4-5-20250929",
                max_tokens=800,
                temperature=0.3,
                system=[
                    {
                        "type": "text",
                        "text": prompt,
                        "cache_control": {"type": "ephemeral"},
                    }
                ],
                messages=[
                    {
                        "role": "user",
                        "content": "Generate insights for this conversation.",
                    }
                ],
            )
            return response.content[0].text
        except Exception as e:
            print(f"[InsightEngine] Error calling Claude API: {e}")
            return "[]"

    async def _call_bedrock_api(self, prompt: str) -> str:
        """Legacy synchronous Bedrock call."""
        try:
            if self._bedrock_client is None:
                import boto3

                self._bedrock_client = boto3.client(
                    service_name="bedrock-runtime", region_name=self.aws_region
                )
            model_id = "arn:aws:bedrock:ap-south-1:144918211563:inference-profile/global.anthropic.claude-haiku-4-5-20251001-v1:0"
            request_body = {
                "anthropic_version": "bedrock-2023-05-31",
                "max_tokens": 600,
                "temperature": 0.3,
                "system": [
                    {
                        "type": "text",
                        "text": prompt,
                        "cache_control": {"type": "ephemeral"},
                    }
                ],
                "messages": [
                    {
                        "role": "user",
                        "content": "Generate insights for this conversation.",
                    }
                ],
            }
            response = self._bedrock_client.invoke_model(
                modelId=model_id, body=json.dumps(request_body)
            )
            response_body = json.loads(response["body"].read())
            return response_body["content"][0]["text"]
        except Exception as e:
            print(f"[InsightEngine] Error calling Bedrock API: {e}")
            return "[]"

    async def _call_gemini_api(self, prompt: str) -> str:
        if not self.gcp_project_id:
            return json.dumps(
                [
                    {
                        "type": "suggestion",
                        "text": "Consider offering a restructured payment plan",
                        "priority": "high",
                        "reasoning": "mock",
                    }
                ]
            )
        try:
            if self._gemini_client is None:
                from vertexai.generative_models import GenerativeModel
                import vertexai
                from google.oauth2 import service_account

                credentials = None
                if self.google_application_credentials_json:
                    import json as json_module

                    creds_dict = json_module.loads(
                        self.google_application_credentials_json
                    )
                    credentials = service_account.Credentials.from_service_account_info(
                        creds_dict
                    )
                elif self.google_application_credentials:
                    credentials = service_account.Credentials.from_service_account_file(
                        self.google_application_credentials
                    )
                vertexai.init(
                    project=self.gcp_project_id,
                    location=self.gcp_location,
                    credentials=credentials,
                )
                self._gemini_client = GenerativeModel(self.gemini_model)
            response = await self._gemini_client.generate_content_async(
                contents=f"{prompt}\n\nGenerate insights for this conversation.",
                generation_config={"temperature": 0.3, "max_output_tokens": 600},
            )
            return response.text
        except Exception as e:
            print(f"[InsightEngine] Error calling Vertex AI Gemini: {e}")
            return "[]"

    # ── Conversation summary ────────────────────────────────────────────────

    async def _generate_and_push_periodic_updates(self):
        """Combined periodic task: Generate both Summary Point and overarching AI Insight situations."""
        async with self._summary_lock, self._ai_insight_lock:
            try:
                # ── 1. Update State ──
                # Synchronize both counters to the current total
                self._last_summary_customer_count = self.customer_utterance_count
                self._last_ai_insight_customer_count = self.customer_utterance_count

                # ── 2. Summary Generation (NEW customer turns only) ──
                # We analyze the chunk of customer turns that triggered this update (usually last 4)
                prev_count = self._last_summary_customer_count - self._summary_interval
                customer_turns_seen = 0
                new_customer_lines = []
                for turn in self.transcript:
                    if turn["speaker"] == "customer":
                        customer_turns_seen += 1
                        if customer_turns_seen > prev_count:
                            new_customer_lines.append(
                                f"[{turn.get('time', '')}] CUSTOMER: {turn['text']}"
                            )

                # Customer's preferred language for periodic updates
                periodic_lang_code = self.customer_profile.get("customer", {}).get("preferredLanguage", "en")
                periodic_lang_name = LANGUAGE_NAMES.get(periodic_lang_code, "English")

                if new_customer_lines:
                    transcript_text = "\n".join(new_customer_lines)
                    summary_prompt = f"""You are analyzing a debt collection call. Below are recent CUSTOMER statements.
Extract ONLY genuinely important key points — things that matter for the collection outcome.

INCLUDE (examples):
- Payment commitments: "Will pay CHF 10,000 by Friday"
- Explicit refusals: "I won't pay", "Not my loan"
- Hardship claims: "Lost my job", "Medical emergency"
- Disputes: "Already paid last month", "Wrong amount"
- Settlement requests: "Can I pay lump sum and close?"

DO NOT INCLUDE:
- Generic greetings, acknowledgments, or routine Q&A.
- Anything that doesn't change the collection strategy.

Return ONLY a JSON array with EXACTLY 1 bullet if something important was said: [{{"text":"key point (max 80 chars)","timestamp":"M:SS"}}]
Return [] if nothing noteworthy.
Generate the key point text in {periodic_lang_name}.

Customer statements:
{transcript_text}"""

                    summary_resp = await self._call_summary_llm(summary_prompt)
                    if summary_resp:
                        cleaned = re.sub(
                            r"^```(?:json)?\s*|\s*```$",
                            "",
                            summary_resp.strip(),
                            flags=re.MULTILINE,
                        ).strip()
                        arr_start = cleaned.find("[")
                        arr_end = cleaned.rfind("]")
                        if arr_start != -1 and arr_end != -1:
                            try:
                                new_summary_items = json.loads(
                                    cleaned[arr_start : arr_end + 1]
                                )
                                for item in new_summary_items:
                                    if isinstance(item, dict) and "text" in item:
                                        self._summary_items.append(
                                            {
                                                "text": str(item["text"])[:100],
                                                "timestamp": str(
                                                    item.get("timestamp", "")
                                                ),
                                            }
                                        )
                            except Exception as e:
                                print(
                                    f"[InsightEngine] Failed to parse summary JSON: {e}"
                                )

                # ── 3. AI Insight Generation (Situation Summary) ──
                # AI insights use a broader context (last 8 turns) to capture the situation
                transcript_context = preprocess_transcript(self.transcript, 8)
                if transcript_context:
                    insight_prompt = f"""You are an AI debt collection assistant. Analyze the recent conversation and generate exactly 1 short, crisp AI insight about the current situation.

Keep it under 80 characters. Be direct and actionable, like a sticky note.
Examples: "Customer stalling — offer settlement", "High aggression — de-escalate tone", "PTP likely — confirm date and amount"

Return ONLY a JSON array: [{{"text":"short crisp insight (max 80 chars)","timestamp":"M:SS"}}]
If no insight, return [].
Generate the insight text in {periodic_lang_name}.

Recent conversation:
{chr(10).join(transcript_context)}"""

                    insight_resp = await self._call_summary_llm(insight_prompt)
                    if insight_resp:
                        cleaned = re.sub(
                            r"^```(?:json)?\s*|\s*```$",
                            "",
                            insight_resp.strip(),
                            flags=re.MULTILINE,
                        ).strip()
                        arr_start = cleaned.find("[")
                        arr_end = cleaned.rfind("]")
                        if arr_start != -1 and arr_end != -1:
                            try:
                                new_insight_items = json.loads(
                                    cleaned[arr_start : arr_end + 1]
                                )
                                time_str = datetime.now().strftime("%H:%M:%S")
                                for item in new_insight_items:
                                    if isinstance(item, dict) and "text" in item:
                                        self._ai_insights.append(
                                            {
                                                "insightId": f"ins-{int(time.time())}-{len(self._ai_insights)}",
                                                "type": "insight",
                                                "text": str(item["text"])[:100],
                                                "priority": "medium",
                                                "reasoning": "",
                                                "source_layer": "insight-engine",
                                                "time": item.get("timestamp", time_str),
                                            }
                                        )
                            except Exception as e:
                                print(
                                    f"[InsightEngine] Failed to parse insight JSON: {e}"
                                )

                # ── 4. Unified Push ──
                await self._push_combined_summary()

            except Exception as e:
                print(f"[InsightEngine] Error in periodic updates: {e}")

    async def _call_summary_llm(self, prompt: str) -> str:
        """Call the configured LLM for summary generation (lightweight, non-streaming)."""
        try:
            if self.ai_provider == "cerebras":
                if not self.cerebras_api_key:
                    return "[]"
                if self._cerebras_client is None:
                    from cerebras.cloud.sdk import AsyncCerebras

                    self._cerebras_client = AsyncCerebras(api_key=self.cerebras_api_key)
                resp = await self._cerebras_client.chat.completions.create(
                    model=self.cerebras_model,
                    max_tokens=300,
                    temperature=0.2,
                    messages=[{"role": "user", "content": prompt}],
                )
                return resp.choices[0].message.content

            elif self.ai_provider == "bedrock":
                if self._bedrock_client is None:
                    import boto3
                    from botocore.config import Config

                    self._bedrock_client = boto3.client(
                        "bedrock-runtime",
                        region_name=self.aws_region,
                        config=Config(
                            retries={"max_attempts": 2, "mode": "adaptive"},
                            read_timeout=10,
                            connect_timeout=5,
                        ),
                    )
                model_id = "arn:aws:bedrock:ap-south-1:144918211563:inference-profile/global.anthropic.claude-haiku-4-5-20251001-v1:0"
                body = json.dumps(
                    {
                        "anthropic_version": "bedrock-2023-05-31",
                        "max_tokens": 300,
                        "messages": [{"role": "user", "content": prompt}],
                        "temperature": 0.2,
                    }
                )
                loop = asyncio.get_event_loop()

                def _invoke():
                    resp = self._bedrock_client.invoke_model(
                        modelId=model_id, body=body, contentType="application/json"
                    )
                    result = json.loads(resp["body"].read())
                    return result["content"][0]["text"]

                return await loop.run_in_executor(None, _invoke)

            elif self.ai_provider == "openai":
                if not self.openai_api_key:
                    return "[]"
                if self._openai_client is None:
                    from openai import AsyncOpenAI

                    self._openai_client = AsyncOpenAI(api_key=self.openai_api_key)
                resp = await self._openai_client.chat.completions.create(
                    model="gpt-5-nano-2025-08-07",
                    max_tokens=300,
                    temperature=0.2,
                    messages=[{"role": "user", "content": prompt}],
                )
                return resp.choices[0].message.content

            elif self.ai_provider == "gemini":
                if not self.gcp_project_id:
                    return "[]"
                if self._gemini_client is None:
                    from vertexai.generative_models import GenerativeModel
                    import vertexai
                    from google.oauth2 import service_account

                    credentials = None
                    if self.google_application_credentials_json:
                        creds_dict = json.loads(
                            self.google_application_credentials_json
                        )
                        credentials = (
                            service_account.Credentials.from_service_account_info(
                                creds_dict
                            )
                        )
                    elif self.google_application_credentials:
                        credentials = (
                            service_account.Credentials.from_service_account_file(
                                self.google_application_credentials
                            )
                        )
                    vertexai.init(
                        project=self.gcp_project_id,
                        location=self.gcp_location,
                        credentials=credentials,
                    )
                    self._gemini_client = GenerativeModel(self.gemini_model)
                resp = await self._gemini_client.generate_content_async(
                    contents=prompt,
                    generation_config={"temperature": 0.2, "max_output_tokens": 300},
                )
                return resp.text

            else:  # claude
                if not self.anthropic_api_key:
                    return "[]"
                if self._claude_client is None:
                    from anthropic import AsyncAnthropic

                    self._claude_client = AsyncAnthropic(api_key=self.anthropic_api_key)
                resp = await self._claude_client.messages.create(
                    model="claude-sonnet-4-5-20250929",
                    max_tokens=300,
                    temperature=0.2,
                    messages=[{"role": "user", "content": prompt}],
                )
                return resp.content[0].text

        except Exception as e:
            print(f"[Summary] LLM call failed: {e}")
            return ""

    async def _push_combined_summary(self):
        """POST combined summary and insights to backend (Unified Section)."""
        try:
            payload = {
                "callSid": self.call_sid,
                "mobileNumber": self.mobile_number,
                "summaryItems": self._summary_items,
                "insightItems": self._ai_insights,
            }
            url = f"{self.backend_url}/collassistantapi/transcript/summary"
            async with self.http_session.post(url, json=payload) as resp:
                if resp.status == 200:
                    print(
                        f"[SummaryCombined] Pushed {len(self._summary_items)} summaries and {len(self._ai_insights)} insights"
                    )
                else:
                    print(f"[SummaryCombined] Failed to push: {resp.status}")
        except Exception as e:
            print(f"[SummaryCombined] Error pushing combined summary: {e}")

    def _truncate_copilot_response(self, copilot_data: Dict) -> Dict:
        """Truncate legacy copilot response fields to Java validation limits."""
        if copilot_data.get("next_move"):
            nm = copilot_data["next_move"]
            if nm.get("points"):
                nm["points"] = nm["points"][:2]
        for warning in copilot_data.get("warnings", []):
            if warning.get("text") and len(warning["text"]) > 250:
                warning["text"] = warning["text"][:247] + "..."
        for insight in copilot_data.get("insights", []):
            if insight.get("text") and len(insight["text"]) > 250:
                insight["text"] = insight["text"][:247] + "..."
        if copilot_data.get("disposition"):
            disp = copilot_data["disposition"]
            if disp.get("notes") and len(disp["notes"]) > 150:
                disp["notes"] = disp["notes"][:147] + "..."
            if disp.get("reasoning") and len(disp["reasoning"]) > 250:
                disp["reasoning"] = disp["reasoning"][:247] + "..."
        return copilot_data

    @staticmethod
    def build_copilot_prompt(
        customer: dict,
        loan: dict,
        additional: dict,
        payment_toon: str,
        policy_lines: list[str],
        recent_count: int,
        transcript_lines: list[str],
        include_disposition: bool = True,
        include_contextual: bool = True,
        call_flow_text: str = "",
        preferred_language: str = "en",
        prediction_line: str = "",
    ) -> tuple[str, str]:
        """(A2) v2 copilot prompt — aggressive compression for latency."""
        schema_dict = {"next_move": {"points": ["max 2"], "priority": "high|medium|low"}}
        if include_contextual:
            schema_dict["contextual_details"] = {
                "details": [{"label": "<18ch field name", "value": "<20ch raw number/fact", "highlight": "bool"}]
            }
            schema_dict["insights"] = [
                {
                    "type": "intent",
                    "text": "Customer shows payment intent",
                    "priority": "high",
                    "reasoning": "clear commitment"
                }
            ]
        if include_disposition:
            schema_dict["disposition"] = {
                "result": "PTP|Won't Pay|Can't Pay|Wrong|Invalid|Not Reachable|Not Picking",
                "conf": "0-1",
                "date": "YYYY-MM-DD|null",
                "amt": "num",
                "reason": "Job|Business|Medical|Bank|Wrong EMI|null",
                "notes": "<150ch",
                "next": "Follow-up|Link|Supervisor|Legal|None",
            }

        system_prompt = f"""Real-time debt collection copilot. Return JSON only.
{json.dumps(schema_dict)}
Rules:
insights: 1-3 NEW observations from the transcript. Use types: intent (customer intent), suggestion (agent action), policy (policy reminder), alert (risk/flag), sentiment (customer mood). Return empty array if nothing new.
contextual_details: 3-5 items from profile relevant to last customer statement.
STRICT FORMAT — label: short field name (max 18 chars). value: raw number/fact ONLY (max 20 chars). NEVER write sentences, analysis, or semicolons in value.
GOOD: {{"label":"DPD","value":"67 days","highlight":true}}, {{"label":"Overdue","value":"CHF 73,800","highlight":true}}, {{"label":"Last Paid","value":"Dec CHF 5K","highlight":false}}, {{"label":"EMI","value":"CHF 18,450","highlight":false}}, {{"label":"Bounce Charges","value":"CHF 1,500","highlight":false}}
BAD (NEVER DO THIS): {{"value":"Aug bounced; Sep cleared; liquidity stress"}}, {{"value":"eligible for plan, not settlement"}}, {{"value":"3 missed in last 6 months"}}
Use ONLY provided data. No fabrication. Follow the call flow decision tree steps.
ML SIGNAL: The CALL CONTEXT "ML:" line carries model-predicted probabilities — PTP-fulfil (likelihood the customer keeps a promise to pay), pay-in-15d and pay-in-30d (likelihood of payment within that window), each with a band (high/mid/low). Treat these as a strong signal that MUST inform next_move priority, insights, and disposition. Low PTP-fulfil → make next_move firmer (push for immediate/secured commitment) and set disposition conf lower for PTP; high PTP-fulfil → support a PTP path and a follow-up next action. Align pay-in-15d/30d with any proposed payment timeline. Never state the raw percentages to the customer; use them only to shape your guidance.
MANDATORY POLICY ENFORCEMENT: The POLICIES section in CALL CONTEXT contains hard bank policy rules. You MUST follow them exactly in every next_move suggestion. Never suggest a repayment amount, timeline, or offer that contradicts any policy rule. If a policy specifies exact payment terms (e.g. 50% today + balance in 7 days), the agent must offer exactly those terms — no flexibility, no alternatives, no exceptions. Always use Today's date (in CALL CONTEXT) to compute and state exact calendar dates — never say "in 7 days" or "by next week", always say the actual date (e.g. "by 28 May 2026").
If the conversation indicates the customer is questioning payments, disputing amounts, or the agent needs payment context — surface payment history in contextual_details as TWO separate items: one for paid months and one for unpaid months (e.g. {{"label":"Paid Months","value":"Jun CHF 5K, Aug CHF 5K","highlight":false}}, {{"label":"Unpaid Months","value":"Jul ✗, Sep ✗","highlight":true}}).
LANGUAGE: Generate next_move points and contextual_details labels in {LANGUAGE_NAMES.get(preferred_language, "English")}. Keep field values (amounts, dates, numbers) in their original format."""

        # ── Static CALL CONTEXT — precooked once, lives in the cached prefix ──────
        # Customer profile, ML scores, policies and call-flow are constant for the
        # whole call, so they are appended to the SYSTEM prompt (the provider's
        # cached prefix / "LLM memory") and reused every turn instead of being
        # re-sent mid-conversation. Only the transcript (user prompt) changes.
        today = datetime.now().strftime("%d %b %Y")
        flow_section = f"\nFlow:\n{call_flow_text}" if call_flow_text else ""
        ml_line = f"\nML:{prediction_line}" if prediction_line else ""
        system_prompt += f"""

--- CALL CONTEXT (static for this call) ---
Today:{today}
Cust:{customer.get("name", "")} Agr:{customer.get("agreementId", "")} Loan:{loan.get("amount", "")} Ten:{customer.get("loanType", "")}
Outs:{loan.get("outstanding", "")} Due:{loan.get("overdue", "")} DPD:{additional.get("dpd", 0)}d EMI:CHF {additional.get("amount", "")}{ml_line}
Pay:
{payment_toon}
POLICIES (MANDATORY - HARD RULES, NO EXCEPTIONS):
{chr(10).join(policy_lines)}{flow_section}
Answer rules:
- points: 1-2 cues. NOT dialogue.
- Follow the call flow decision tree steps."""

        user_prompt = InsightEngine.build_user_prompt(transcript_lines, recent_count)
        # print(f"[InsightEngine] Built v2 prompts (system {len(system_prompt)} chars, user {len(user_prompt)} chars)")
        return system_prompt, user_prompt

    @staticmethod
    def build_user_prompt(transcript_lines: list[str], recent_count: int) -> str:
        """Dynamic v2 user prompt: only the live transcript, which changes every
        turn. Kept minimal so the static system prefix stays cache-hot — the static
        customer context lives in the system prompt (see build_copilot_prompt)."""
        return f"""Trans (last {recent_count} turns):
{chr(10).join(transcript_lines)}"""


# ── Legacy response parsers ──────────────────────────────────────────────────


def parse_insight_response(response: str) -> tuple[list, dict | None]:
    """Parse legacy insight JSON response. Returns (insights_list, disposition_or_None)."""
    try:
        response = response.strip()
        for fence in ["```json", "```"]:
            if response.startswith(fence):
                response = response[len(fence) :]
        if response.endswith("```"):
            response = response[:-3]
        response = response.strip()

        json_start = next((i for i, c in enumerate(response) if c in "{["), -1)
        if json_start == -1:
            return [], None

        from json import JSONDecoder

        parsed, _ = JSONDecoder().raw_decode(response, json_start)

        if isinstance(parsed, dict):
            insights = parsed.get("insights", [])
            return (insights if isinstance(insights, list) else []), parsed.get(
                "disposition"
            )
        elif isinstance(parsed, list):
            return parsed, None
        return [], None
    except Exception as e:
        print(f"[InsightEngine] Error parsing insight response: {e}")
        return [], None


def parse_copilot_response(response: str) -> dict | None:
    """Parse legacy combined copilot JSON response."""
    try:
        response = response.strip()
        for fence in ["```json", "```"]:
            if response.startswith(fence):
                response = response[len(fence) :]
        if response.endswith("```"):
            response = response[:-3]
        response = response.strip()

        json_start = next((i for i, c in enumerate(response) if c == "{"), -1)
        if json_start == -1:
            return None

        from json import JSONDecoder

        parsed, _ = JSONDecoder().raw_decode(response, json_start)

        if not isinstance(parsed, dict):
            return None

        result = {
            "next_move": parsed.get("next_move"),
            "warnings": parsed.get("warnings", []),
            "insights": parsed.get("insights", []),
            "disposition": parsed.get("disposition"),
        }

        if not result["next_move"]:
            return None
        if not isinstance(result["warnings"], list):
            result["warnings"] = []
        if not isinstance(result["insights"], list):
            result["insights"] = []

        return result
    except Exception as e:
        print(f"[CopilotParser] Error parsing copilot response: {e}")
        return None
