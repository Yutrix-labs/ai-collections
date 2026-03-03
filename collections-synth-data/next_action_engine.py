"""
next_action_engine.py
Rules-based engine that recommends the next collection action for an account.

Two-phase design:
  Phase 1 — Hard Rule Cascade: inviolable domain rules checked in priority order.
             First match short-circuits; no scoring needed.
  Phase 2 — Weighted Scoring Pass: when no hard rule fires, six independent
             signal groups score all candidate actions; highest total wins.

All optional module fields are guarded with .get() — the engine degrades
gracefully to core-only records.
"""

from __future__ import annotations

from domain_definitions import (
    BASE_PAID_PROB,
    NEXT_ACTIONS,
    ACTION_TO_CHANNEL,
    DPD_SEVERITY_SCORE,
    ACTION_SIGNAL_WEIGHTS,
    PRIORITY_THRESHOLDS,
)

# ---------------------------------------------------------------------------
# DPD bucket label → key mapping (inverse of DPD_BUCKETS label field)
# ---------------------------------------------------------------------------
_DPD_LABEL_TO_KEY = {
    "Current":          "current",
    "Early (1-30)":     "early",
    "Mild (31-60)":     "mild",
    "Severe (61-90)":   "severe",
    "NPA (90+)":        "npa",
    # accept raw keys too (for test convenience)
    "current":          "current",
    "early":            "early",
    "mild":             "mild",
    "severe":           "severe",
    "npa":              "npa",
}

_EARLY_DPD_BUCKETS = {"current", "early"}
_MILD_OR_LIGHTER    = {"current", "early", "mild"}
_NPA_BUCKETS        = {"severe", "npa"}


def _dpd_key(record: dict) -> str:
    """Normalise dpd_bucket to a canonical key string."""
    raw = record.get("dpd_bucket", "current")
    return _DPD_LABEL_TO_KEY.get(raw, "current")


# ---------------------------------------------------------------------------
# Phase 1 — Hard Rule Cascade
# ---------------------------------------------------------------------------

def _apply_hard_rules(record: dict) -> dict | None:
    """Check inviolable domain rules in priority order.

    Returns a full result dict on the first match, or None if no rule fires.
    """
    status           = record.get("resolution_status", "Open")
    dpd_key          = _dpd_key(record)
    risk_tier        = record.get("risk_tier", "prime")
    contact_attempts = record.get("contact_attempts", 0)
    promise_to_pay   = record.get("promise_to_pay", False)
    escalation_flag  = record.get("escalation_flag", False)
    do_not_disturb   = record.get("do_not_disturb", False)
    self_cure_prob   = record.get("self_cure_probability", None)

    # Rule 1 — Written-off → CLOSE_ACCOUNT
    if status == "Written-off":
        return _hard_result("CLOSE_ACCOUNT", 0.99,
                            "Account is written off; no further collection action required.")

    # Rule 2 — Settled → CLOSE_ACCOUNT
    if status == "Settled":
        return _hard_result("CLOSE_ACCOUNT", 0.99,
                            "Account is fully settled; close account.")

    # Rule 3 — Do-Not-Disturb registered → MONITOR
    if do_not_disturb:
        return _hard_result("MONITOR", 0.90,
                            "Borrower has registered DND; cannot initiate outbound contact.")

    # Rule 4 — Legal status → SEND_LEGAL_NOTICE
    if status == "Legal":
        return _hard_result("SEND_LEGAL_NOTICE", 0.95,
                            "Account is in legal proceedings; escalate with legal notice.")

    # Rule 5 — NPA bucket + ≥15 attempts + escalation flag → SEND_LEGAL_NOTICE
    if dpd_key in _NPA_BUCKETS and contact_attempts >= 15 and escalation_flag:
        return _hard_result("SEND_LEGAL_NOTICE", 0.88,
                            "NPA account with 15+ contact attempts and escalation flag; legal notice required.")

    # Rule 6 — PTP + promise_to_pay + early DPD → MONITOR
    if promise_to_pay and dpd_key in _EARLY_DPD_BUCKETS:
        return _hard_result("MONITOR", 0.85,
                            "Promise to pay confirmed; monitor for self-resolution.")

    # Rule 7 — High self-cure probability (>0.60) + current DPD → MONITOR
    if self_cure_prob is not None and self_cure_prob > 0.60 and dpd_key == "current":
        return _hard_result("MONITOR", 0.80,
                            f"High self-cure probability ({self_cure_prob:.0%}); allow self-resolution.")

    # Rule 8 — PTP status + DPD ≤ mild (but promise_to_pay not set) → CALL_BACK
    if status == "PTP" and dpd_key in _MILD_OR_LIGHTER:
        return _hard_result("CALL_BACK", 0.82,
                            "PTP status recorded; schedule a follow-up call to confirm payment.")

    # Rule 9 — Zero contacts + current DPD + prime/near_prime → MONITOR
    if contact_attempts == 0 and dpd_key == "current" and risk_tier in {"prime", "near_prime"}:
        return _hard_result("MONITOR", 0.75,
                            "No contact attempted yet; prime/near-prime borrower likely to self-cure.")

    # Rule 10 — Zero contacts + current DPD + sub_prime/npa → SEND_SMS
    if contact_attempts == 0 and dpd_key == "current" and risk_tier in {"sub_prime", "npa"}:
        return _hard_result("SEND_SMS", 0.72,
                            "No contact attempted yet; send an SMS nudge for sub-prime/NPA borrower.")

    return None


def _hard_result(action: str, confidence: float, reason: str) -> dict:
    priority = _confidence_to_priority(confidence)
    return {
        "next_action":   action,
        "channel":       ACTION_TO_CHANNEL[action],
        "reason":        reason,
        "priority":      priority,
        "confidence":    confidence,
        "action_scores": {action: confidence},
    }


# ---------------------------------------------------------------------------
# Phase 2 — Weighted Scoring Pass
# ---------------------------------------------------------------------------

def _score_actions(record: dict) -> dict[str, float]:
    """Compute a weighted score for each candidate action.

    Six signal groups each return a per-action score dict {action: 0..1}.
    Scores are combined via the ACTION_SIGNAL_WEIGHTS weight vector.
    """
    signals = [
        _signal_paid_prob(record),
        _signal_dpd_severity(record),
        _signal_payment_history(record),
        _signal_response(record),
        _signal_channel_availability(record),
        _signal_recovery_potential(record),
    ]

    totals: dict[str, float] = {}
    for action in NEXT_ACTIONS:
        weights = ACTION_SIGNAL_WEIGHTS[action]
        score = sum(w * s.get(action, 0.0) for w, s in zip(weights, signals))
        totals[action] = round(score, 6)

    return totals


# --- Signal 1: Paid probability ---

def _signal_paid_prob(record: dict) -> dict[str, float]:
    """High paid probability → MONITOR/light; low → escalate."""
    risk_tier = record.get("risk_tier", "prime")
    dpd_key   = _dpd_key(record)
    prob = BASE_PAID_PROB.get(risk_tier, {}).get(dpd_key, 0.50)

    # Normalise: prob ∈ [0,1] — high prob favours light actions
    light_score  = prob          # MONITOR, SMS, email, whatsapp
    heavy_score  = 1.0 - prob    # FIELD_VISIT, LEGAL, OFFER_SETTLEMENT
    mid_score    = 0.5           # CALL_BACK

    return {
        "MONITOR":           light_score,
        "SEND_SMS":          light_score * 0.8,
        "SEND_WHATSAPP":     light_score * 0.8,
        "SEND_EMAIL":        light_score * 0.8,
        "CALL_BACK":         mid_score,
        "FIELD_VISIT":       heavy_score * 0.8,
        "SEND_LEGAL_NOTICE": heavy_score,
        "OFFER_SETTLEMENT":  heavy_score * 0.7,
        "CLOSE_ACCOUNT":     0.0,
    }


# --- Signal 2: DPD severity ---

def _signal_dpd_severity(record: dict) -> dict[str, float]:
    """Higher DPD severity → field/legal; lower → monitor."""
    dpd_key  = _dpd_key(record)
    severity = DPD_SEVERITY_SCORE.get(dpd_key, 0)   # 0–4
    norm     = severity / 4.0                         # 0.0–1.0

    return {
        "MONITOR":           1.0 - norm,
        "SEND_SMS":          0.6 - norm * 0.4,
        "SEND_WHATSAPP":     0.6 - norm * 0.4,
        "SEND_EMAIL":        0.6 - norm * 0.4,
        "CALL_BACK":         0.5,
        "FIELD_VISIT":       norm,
        "SEND_LEGAL_NOTICE": norm,
        "OFFER_SETTLEMENT":  norm * 0.8,
        "CLOSE_ACCOUNT":     0.0,
    }


# --- Signal 3: Payment history pattern ---

def _signal_payment_history(record: dict) -> dict[str, float]:
    """Last-3-char pattern of payment_history_12m."""
    hist   = record.get("payment_history_12m", "")
    last3  = hist[-3:] if len(hist) >= 3 else hist

    p_count = last3.count("P")
    m_count = last3.count("M")

    # PPP → positive signal for light actions
    # MMM → positive signal for escalated actions
    # Mixed → neutral
    ppp_score = p_count / 3.0
    mmm_score = m_count / 3.0

    return {
        "MONITOR":           ppp_score,
        "SEND_SMS":          0.5 - mmm_score * 0.2,
        "SEND_WHATSAPP":     0.5 - mmm_score * 0.2,
        "SEND_EMAIL":        0.5 - mmm_score * 0.2,
        "CALL_BACK":         0.5,
        "FIELD_VISIT":       mmm_score,
        "SEND_LEGAL_NOTICE": mmm_score,
        "OFFER_SETTLEMENT":  mmm_score * 0.8,
        "CLOSE_ACCOUNT":     0.0,
    }


# --- Signal 4: Response signal ---

def _signal_response(record: dict) -> dict[str, float]:
    """Low response/pickup → escalate channel or field; high → lighter."""
    response_rate    = record.get("response_rate",    0.60)
    call_pickup_rate = record.get("call_pickup_rate", 0.60)

    # Last action outcome from action_history
    action_history = record.get("action_history", [])
    last_outcome   = action_history[-1]["outcome"] if action_history else None

    low_response = 1.0 - min(response_rate, call_pickup_rate)   # 0 = very responsive

    # Boost escalation if last outcome was NO_RESPONSE
    legal_boost = 0.30 if last_outcome == "NO_RESPONSE" else 0.0

    return {
        "MONITOR":           1.0 - low_response,
        "SEND_SMS":          0.5,
        "SEND_WHATSAPP":     0.5,
        "SEND_EMAIL":        0.5,
        "CALL_BACK":         1.0 - low_response * 0.6,
        "FIELD_VISIT":       low_response,
        "SEND_LEGAL_NOTICE": min(1.0, low_response + legal_boost),
        "OFFER_SETTLEMENT":  min(1.0, low_response * 0.6 + legal_boost * 0.5),
        "CLOSE_ACCOUNT":     0.0,
    }


# --- Signal 5: Channel availability ---

def _signal_channel_availability(record: dict) -> dict[str, float]:
    """Enable/disable channel actions based on comm module fields."""
    whatsapp  = record.get("whatsapp_opted_in", False)
    email_ok  = record.get("email_deliverable", True)
    preferred = record.get("preferred_channel", None)

    wa_score    = 1.0 if whatsapp else 0.0
    email_score = 1.0 if email_ok else 0.0

    preferred_sms  = 1.2 if preferred == "sms"       else 1.0
    preferred_wa   = 1.2 if preferred == "whatsapp"   else 1.0
    preferred_call = 1.2 if preferred == "phone"      else 1.0
    preferred_field = 1.2 if preferred == "field"     else 1.0

    return {
        "MONITOR":           1.0,
        "SEND_SMS":          min(1.0, 0.8 * preferred_sms),
        "SEND_WHATSAPP":     min(1.0, wa_score * preferred_wa),
        "SEND_EMAIL":        email_score,
        "CALL_BACK":         min(1.0, 0.9 * preferred_call),
        "FIELD_VISIT":       min(1.0, 0.7 * preferred_field),
        "SEND_LEGAL_NOTICE": 1.0,
        "OFFER_SETTLEMENT":  1.0,
        "CLOSE_ACCOUNT":     1.0,
    }


# --- Signal 6: Recovery potential ---

def _signal_recovery_potential(record: dict) -> dict[str, float]:
    """High collateral / good LTV → settlement or legal viable."""
    collateral_value = record.get("collateral_value", 0.0)
    ltv_ratio        = record.get("ltv_ratio", 0.0)
    condition        = record.get("collateral_condition", "N/A")

    has_collateral   = collateral_value > 0
    good_condition   = condition in {"Good", "Fair"}
    recoverable_ltv  = ltv_ratio < 0.90 if has_collateral else False

    if has_collateral and good_condition and recoverable_ltv:
        recovery_score = 1.0
    elif has_collateral and (good_condition or recoverable_ltv):
        recovery_score = 0.60
    elif has_collateral:
        recovery_score = 0.30
    else:
        recovery_score = 0.0

    return {
        "MONITOR":           0.3,
        "SEND_SMS":          0.3,
        "SEND_WHATSAPP":     0.3,
        "SEND_EMAIL":        0.3,
        "CALL_BACK":         0.5,
        "FIELD_VISIT":       recovery_score * 0.7,
        "SEND_LEGAL_NOTICE": recovery_score,
        "OFFER_SETTLEMENT":  recovery_score,
        "CLOSE_ACCOUNT":     0.0,
    }


# ---------------------------------------------------------------------------
# Channel selection
# ---------------------------------------------------------------------------

def _select_channel(record: dict, action: str) -> str | None:
    """Map action to the best available channel using comm module fields."""
    default = ACTION_TO_CHANNEL.get(action)

    # Actions with fixed channels
    if action in {"MONITOR", "CLOSE_ACCOUNT"}:
        return None
    if action == "SEND_LEGAL_NOTICE":
        return "legal"
    if action == "FIELD_VISIT":
        return "field"

    # SEND_WHATSAPP requires opt-in
    if action == "SEND_WHATSAPP":
        return "whatsapp" if record.get("whatsapp_opted_in", False) else "sms"

    # SEND_EMAIL requires deliverable address
    if action == "SEND_EMAIL":
        return "email" if record.get("email_deliverable", True) else "sms"

    # CALL_BACK / OFFER_SETTLEMENT — respect preferred_channel if available
    if action in {"CALL_BACK", "OFFER_SETTLEMENT"}:
        preferred = record.get("preferred_channel")
        if preferred in {"phone", "whatsapp"}:
            if preferred == "whatsapp" and record.get("whatsapp_opted_in", False):
                return "whatsapp"
            return "phone"
        return "phone"

    return default


# ---------------------------------------------------------------------------
# Result builder
# ---------------------------------------------------------------------------

def _build_result(
    action: str,
    channel: str | None,
    scores: dict[str, float],
    record: dict,
    reason: str,
    confidence: float,
) -> dict:
    priority = _confidence_to_priority(confidence)
    return {
        "next_action":   action,
        "channel":       channel,
        "reason":        reason,
        "priority":      priority,
        "confidence":    round(confidence, 4),
        "action_scores": scores,
    }


def _confidence_to_priority(confidence: float) -> str:
    if confidence >= PRIORITY_THRESHOLDS["HIGH"]:
        return "HIGH"
    if confidence >= PRIORITY_THRESHOLDS["MEDIUM"]:
        return "MEDIUM"
    return "LOW"


def _build_reason(action: str, scores: dict[str, float], record: dict) -> str:
    """Generate a human-readable reason string for a scored action."""
    dpd_key   = _dpd_key(record)
    risk_tier = record.get("risk_tier", "prime")
    hist      = record.get("payment_history_12m", "")
    last3     = hist[-3:] if len(hist) >= 3 else hist

    reasons = {
        "MONITOR": (
            f"Account is {dpd_key}-DPD with risk tier '{risk_tier}'; "
            "scoring favours a watch-and-wait approach."
        ),
        "SEND_SMS": (
            f"Low-cost proactive nudge recommended for {risk_tier} tier "
            f"at {dpd_key}-DPD stage."
        ),
        "SEND_WHATSAPP": (
            f"Borrower has WhatsApp opt-in; WhatsApp outreach preferred "
            f"for {risk_tier} / {dpd_key}-DPD."
        ),
        "SEND_EMAIL": (
            f"Email is deliverable; digital outreach recommended for "
            f"{dpd_key}-DPD account."
        ),
        "CALL_BACK": (
            f"Follow-up call recommended; account shows engagement signals "
            f"at {dpd_key}-DPD."
        ),
        "FIELD_VISIT": (
            f"Digital channels underperforming for {risk_tier} / {dpd_key}-DPD account; "
            "field visit recommended."
        ),
        "SEND_LEGAL_NOTICE": (
            f"Account in {dpd_key}-DPD with poor response history (last 3: {last3}); "
            "legal escalation indicated."
        ),
        "OFFER_SETTLEMENT": (
            f"Collateral recovery potential detected for {risk_tier} / {dpd_key}-DPD; "
            "settlement offer may unlock resolution."
        ),
        "CLOSE_ACCOUNT": (
            "Account meets closure criteria (written-off or settled)."
        ),
    }
    return reasons.get(action, f"Action '{action}' selected by scoring engine.")


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def suggested_next_action(record: dict) -> dict:
    """Return a recommended next collection action for the given account record.

    Args:
        record: A dict produced by generate_record() (any combination of
                core + optional schema modules). All optional fields are
                accessed via .get() so the function degrades gracefully.

    Returns:
        {
            "next_action":    str,    # e.g. "FIELD_VISIT"
            "channel":        str,    # e.g. "field"  (None for MONITOR/CLOSE)
            "reason":         str,    # human-readable explanation
            "priority":       str,    # "HIGH" / "MEDIUM" / "LOW"
            "confidence":     float,  # 0.0–1.0
            "action_scores":  dict,   # all scores for transparency
        }
    """
    # Phase 1 — Hard rule cascade
    hard = _apply_hard_rules(record)
    if hard is not None:
        return hard

    # Phase 2 — Weighted scoring
    scores = _score_actions(record)

    sorted_actions = sorted(scores.items(), key=lambda kv: kv[1], reverse=True)
    best_action, best_score = sorted_actions[0]
    second_score = sorted_actions[1][1] if len(sorted_actions) > 1 else 0.0

    # Confidence = normalised gap between top and second-best
    max_possible_gap = best_score if best_score > 0 else 1.0
    confidence = min(1.0, (best_score - second_score) / max_possible_gap)

    channel = _select_channel(record, best_action)
    reason  = _build_reason(best_action, scores, record)

    return _build_result(best_action, channel, scores, record, reason, confidence)
