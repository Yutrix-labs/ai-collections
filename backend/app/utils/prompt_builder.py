"""
LLM prompt builder utility.
"""

from typing import List, Dict, Any


def format_payment_history(payment_history: List[Dict]) -> str:
    """Format payment history for prompt."""
    lines = []
    for payment in payment_history:
        date = payment.get('date', '')
        amount = payment.get('amount', 0)
        channel = payment.get('channel', '')
        status = payment.get('status', '')

        line = f"{date}: ₹ {amount:,} {status}"
        if status == 'bounced':
            bounce_reason = payment.get('bounce_reason', '')
            line += f" ({bounce_reason})"
        line += f" — via {channel}"

        lines.append(line)

    return "\n".join(lines)


def format_policy_rules(policy_rules: Dict) -> str:
    """Format policy rules for prompt."""
    lines = []

    penalty_waiver = policy_rules.get('penalty_waiver')
    if penalty_waiver:
        max_percent = penalty_waiver.get('max_percent', 0)
        min_commitment = penalty_waiver.get('min_commitment', 0)
        lines.append(f"- Penalty waiver: Up to {max_percent}% if customer commits ₹ {min_commitment:,}+ within 30 days")

    if not policy_rules.get('legal_reference_allowed', True):
        lines.append("- DO NOT mention legal action for DPD < 90 accounts")

    if policy_rules.get('settlement_eligible'):
        lines.append("- Settlement eligible — customer can request one-time settlement")
    else:
        lines.append("- Settlement not eligible — available after 90+ DPD")

    lines.append("- Maintain empathetic, professional tone. Acknowledge hardship before presenting options.")

    return "\n".join(lines)


def format_transcript(transcript: List[Dict]) -> str:
    """Format transcript for prompt."""
    lines = []

    for utterance in transcript:
        speaker = utterance.get('speaker', 'unknown')
        text = utterance.get('text', '')
        time = utterance.get('time', '')
        sentiment = utterance.get('sentiment', '')

        speaker_label = "AGENT" if speaker == "agent" else "CUSTOMER"
        sentiment_label = f" ({sentiment})" if sentiment and speaker == "customer" else ""

        lines.append(f"[{time}] {speaker_label}{sentiment_label}: {text}")

    return "\n".join(lines)


def format_previous_insights(previous_insights: List[Dict]) -> str:
    """Format previous insights for prompt."""
    if not previous_insights:
        return "(none)"

    lines = []
    for insight in previous_insights:
        time = insight.get('time', '')
        insight_type = insight.get('type', '')
        priority = insight.get('priority', '')
        text = insight.get('text', '')

        lines.append(f"[{time}] {insight_type}/{priority}: \"{text}\"")

    return "\n".join(lines)


def build_llm_prompt(profile: Dict, transcript: List[Dict], previous_insights: List[Dict] = None) -> str:
    """Build complete LLM prompt."""

    if previous_insights is None:
        previous_insights = []

    customer = profile.get('customer', {})
    loan = profile.get('loan', {})
    additional = profile.get('additional', {})
    payment_history = profile.get('payment_history', [])
    active_policies = profile.get('active_policies', {})

    prompt = f"""--- CUSTOMER PROFILE ---
Name: {customer.get('name', '')}
Agreement: {customer.get('agreement_id', '')} | Loan Type: {loan.get('loan_type', '')}
Loan: ₹ {loan.get('amount', 0):,} | Tenure: {loan.get('tenure_months', 0)} months
Outstanding: ₹ {loan.get('outstanding', 0):,} | Overdue: ₹ {loan.get('overdue', 0):,}
DPD: {additional.get('dpd', 0)} days | EMI: ₹ {additional.get('emi_amount', 0):,}

--- PAYMENT HISTORY (last 6 months) ---
{format_payment_history(payment_history)}

--- ACTIVE POLICY RULES ---
{format_policy_rules(active_policies)}

--- LIVE TRANSCRIPT ---
{format_transcript(transcript)}

--- PREVIOUS INSIGHTS THIS CALL ---
{format_previous_insights(previous_insights)}

--- INSTRUCTIONS ---
Generate 1-3 NEW insights. Each must be one of: intent, suggestion, policy, alert, sentiment.
Return JSON array: [{{"type": "intent|suggestion|policy|alert|sentiment", "text": "<120 chars", "priority": "high|medium|low", "reasoning": "brief explanation"}}]
DO NOT repeat previous insights. Return [] if no new insights warranted.

IMPORTANT:
- Use ONLY the data provided in the customer profile. NEVER fabricate amounts, dates, or account numbers.
- Keep text concise and actionable (under 120 characters).
- Priority HIGH for urgent actions, alerts, or critical information.
- Priority MEDIUM for helpful suggestions or policy reminders.
- Priority LOW for sentiment observations or general context.
"""

    return prompt
