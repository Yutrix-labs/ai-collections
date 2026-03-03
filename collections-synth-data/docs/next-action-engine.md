# Next Action Engine — Design Document

**Version:** 1.0
**Date:** 2026-03-03
**File:** `next_action_engine.py`

---

## Overview

The `suggested_next_action` engine is a transparent, rules-based recommender that analyses a collections account record and returns a reasoned recommendation for what the agent should do next.

It is intentionally **not** a black-box ML model. Every recommendation comes with a human-readable reason, a confidence score, and a full breakdown of how each candidate action was scored — so agents and supervisors can understand and trust the output.

---

## Output

The engine returns a single dict:

```python
{
    "next_action":    "FIELD_VISIT",      # recommended action
    "channel":        "field",            # outbound channel (None if no contact)
    "reason":         "Digital channels underperforming...",
    "priority":       "HIGH",             # HIGH / MEDIUM / LOW
    "confidence":     0.84,              # 0.0 – 1.0
    "action_scores":  { ... }            # full score breakdown for transparency
}
```

When wired into `generate_record()` via `schema_modules=["next_action"]`, five flat columns are added to the record:

| Column | Type | Example |
|--------|------|---------|
| `suggested_next_action` | str | `"CALL_BACK"` |
| `next_action_channel` | str / None | `"phone"` |
| `next_action_reason` | str | `"PTP status recorded; schedule a follow-up call..."` |
| `next_action_priority` | str | `"HIGH"` |
| `next_action_confidence` | float | `0.82` |

---

## Candidate Actions

| Action | Default Channel |
|--------|----------------|
| `MONITOR` | — (no outbound) |
| `SEND_SMS` | sms |
| `SEND_WHATSAPP` | whatsapp |
| `SEND_EMAIL` | email |
| `CALL_BACK` | phone |
| `FIELD_VISIT` | field |
| `SEND_LEGAL_NOTICE` | legal |
| `OFFER_SETTLEMENT` | phone |
| `CLOSE_ACCOUNT` | — (no outbound) |

---

## Two-Phase Decision Engine

### Phase 1 — Hard Rule Cascade

Ten inviolable domain rules are checked in strict priority order. The **first rule that matches short-circuits the engine** — no scoring is done.

| Priority | Condition | Recommended Action | Confidence |
|----------|-----------|-------------------|------------|
| 1 | `resolution_status == "Written-off"` | `CLOSE_ACCOUNT` | 0.99 |
| 2 | `resolution_status == "Settled"` | `CLOSE_ACCOUNT` | 0.99 |
| 3 | `do_not_disturb == True` | `MONITOR` | 0.90 |
| 4 | `resolution_status == "Legal"` | `SEND_LEGAL_NOTICE` | 0.95 |
| 5 | NPA/severe bucket + `contact_attempts ≥ 15` + `escalation_flag` | `SEND_LEGAL_NOTICE` | 0.88 |
| 6 | `promise_to_pay == True` + DPD is current or early | `MONITOR` | 0.85 |
| 7 | `self_cure_probability > 0.60` + DPD is current | `MONITOR` | 0.80 |
| 8 | `resolution_status == "PTP"` + DPD ≤ mild | `CALL_BACK` | 0.82 |
| 9 | `contact_attempts == 0` + current DPD + prime/near_prime tier | `MONITOR` | 0.75 |
| 10 | `contact_attempts == 0` + current DPD + sub_prime/npa tier | `SEND_SMS` | 0.72 |

If no hard rule fires, the engine proceeds to Phase 2.

---

### Phase 2 — Weighted Scoring Pass

Six independent signal groups each produce a score between 0 and 1 for every candidate action. These are combined using per-action weight vectors defined in `ACTION_SIGNAL_WEIGHTS` in `domain_definitions.py`.

```
Final score for action A = Σ ( weight[i] × signal[i][A] )   for i in 1..6
```

**Confidence** is the normalised gap between the top-scoring and second-scoring action:
```
confidence = (best_score − second_score) / best_score
```

This means a clear winner produces high confidence; a near-tie produces low confidence.

---

#### Signal 1 — Paid Probability

**Source:** `BASE_PAID_PROB[risk_tier][dpd_bucket]` (from `domain_definitions.py`)

High probability of payment → favours light-touch actions (MONITOR, SMS).
Low probability → favours escalation (FIELD_VISIT, LEGAL_NOTICE).

| Example | Paid prob | Effect |
|---------|-----------|--------|
| prime + current | 0.90 | Strong push toward MONITOR |
| npa + npa | 0.02 | Strong push toward escalation |

---

#### Signal 2 — DPD Severity

**Source:** `dpd_bucket` mapped to integer 0–4 via `DPD_SEVERITY_SCORE`

| Bucket | Severity score |
|--------|---------------|
| current | 0 |
| early | 1 |
| mild | 2 |
| severe | 3 |
| npa | 4 |

Higher severity → FIELD_VISIT and SEND_LEGAL_NOTICE score higher.
Lower severity → MONITOR scores higher.

---

#### Signal 3 — Payment History Pattern

**Source:** last 3 characters of `payment_history_12m`

| Pattern | Effect |
|---------|--------|
| `PPP` (3 consecutive payments) | Lighter actions score higher |
| `MMM` (3 consecutive misses) | Escalated actions score higher |
| Mixed | Neutral |

---

#### Signal 4 — Response Signal

**Source:** `response_rate`, `call_pickup_rate`, last entry in `action_history`

Low pickup rate + low response rate → pushes toward FIELD_VISIT (can't reach by phone).
If the last recorded action outcome was `NO_RESPONSE` → additional boost to SEND_LEGAL_NOTICE and OFFER_SETTLEMENT.

---

#### Signal 5 — Channel Availability

**Source:** `whatsapp_opted_in`, `email_deliverable`, `preferred_channel`

- SEND_WHATSAPP scores 0 if `whatsapp_opted_in == False`
- SEND_EMAIL scores 0 if `email_deliverable == False`
- All channel actions get a 20% boost if they match `preferred_channel`

This prevents the engine from recommending a channel the borrower can't or won't receive.

---

#### Signal 6 — Recovery Potential

**Source:** `collateral_value`, `ltv_ratio`, `collateral_condition`

| Condition | Recovery score |
|-----------|---------------|
| Has collateral + Good/Fair condition + LTV < 0.90 | 1.0 |
| Has collateral + one of the above | 0.60 |
| Has collateral only | 0.30 |
| Unsecured (no collateral) | 0.0 |

High recovery potential boosts OFFER_SETTLEMENT and SEND_LEGAL_NOTICE — there is something to recover.

---

## Priority Mapping

| Confidence range | Priority |
|-----------------|----------|
| ≥ 0.70 | HIGH |
| 0.50 – 0.69 | MEDIUM |
| < 0.50 | LOW |

---

## Graceful Degradation

All optional module fields are accessed via `.get()` with sensible defaults. The engine works correctly with:

- **Core fields only** — uses paid probability and DPD severity
- **Core + behavioural** — adds self-cure, response rate, pickup rate, escalation flag
- **Core + communication** — adds DND check, channel availability scoring
- **Core + collateral** — adds recovery potential scoring
- **All modules** — full signal strength

The more modules are present, the more informed (and higher-confidence) the recommendation.

---

## Key Design Decisions

**Transparency over accuracy**
Every recommendation includes `action_scores` — a full dict of every action's score — so the reasoning is always auditable.

**Hard rules are inviolable**
No scoring can override a hard rule. A DND-registered borrower always gets MONITOR, regardless of DPD or collateral.

**Zero-contact rule**
Current DPD + no contact attempts is split by risk tier: prime/near_prime → MONITOR (self-cure likely); sub_prime/npa → SEND_SMS (proactive nudge needed).

**OFFER_SETTLEMENT scoring**
Scores highly via two independent paths:
1. Severe/NPA DPD + strong collateral (LTV < 0.90, good condition)
2. After a failed legal notice (last action outcome = `NO_RESPONSE`)

Both paths contribute additively, so OFFER_SETTLEMENT naturally wins when both are true.

**Deterministic**
Same record always produces the same recommendation. No randomness in the engine.

**Opt-in only**
Not included in `config_default.json`. Must be explicitly added to `schema_modules`.

---

## Usage

```python
from next_action_engine import suggested_next_action

record = {
    "risk_tier":           "npa",
    "dpd_bucket":          "severe",
    "resolution_status":   "Open",
    "contact_attempts":    8,
    "promise_to_pay":      False,
    "payment_history_12m": "MMMMMMMMMMMM",
    # optional module fields
    "response_rate":       0.10,
    "call_pickup_rate":    0.08,
    "collateral_value":    500_000.0,
    "ltv_ratio":           0.70,
    "collateral_condition": "Good",
}

result = suggested_next_action(record)
# {
#   "next_action":   "OFFER_SETTLEMENT",
#   "channel":       "phone",
#   "reason":        "Collateral recovery potential detected...",
#   "priority":      "HIGH",
#   "confidence":    0.76,
#   "action_scores": { "MONITOR": 0.12, "OFFER_SETTLEMENT": 0.63, ... }
# }
```

---

## Files

| File | Role |
|------|------|
| `next_action_engine.py` | Engine implementation |
| `domain_definitions.py` | Constants: `NEXT_ACTIONS`, `ACTION_TO_CHANNEL`, `DPD_SEVERITY_SCORE`, `ACTION_SIGNAL_WEIGHTS`, `PRIORITY_THRESHOLDS` |
| `tests/test_next_action_engine.py` | 35 TDD tests |
| `config_full.json` | Example config with `"next_action"` in `schema_modules` |
