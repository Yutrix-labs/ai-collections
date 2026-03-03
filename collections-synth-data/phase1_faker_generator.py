"""
phase1_faker_generator.py
Phase 1 rules-based synthetic collections data generator.
Uses Faker[en_IN] for Indian locale PII and Markov chains for payment history.
Source: Fintaar_Collections_SynthData_PR_Plan_v2.docx
"""

import random
import numpy as np
import pandas as pd
from faker import Faker

from next_action_engine import suggested_next_action

from domain_definitions import (
    RISK_TIERS, SEGMENTS, LOAN_TYPES, DPD_BUCKETS,
    MARKOV_MATRICES, MARKOV_INIT, CIBIL_RANGES,
    RESOLUTION_DIST, CONTACT_ATTEMPTS_RANGES, OUTSTANDING_RANGES,
    BASE_PAID_PROB, DEFAULT_DPD_WEIGHTS, DEFAULT_SEGMENT_WEIGHTS,
    DEFAULT_RISK_WEIGHTS,
    # interactions
    ACTION_TYPES, ACTION_OUTCOMES, ACTION_CHANNEL_MAP, PAYMENT_CHANNELS,
    PAYMENT_CHANNEL_WEIGHTS, PAYMENT_TYPES, ACTION_COUNT_RANGES,
    ACTION_TYPE_WEIGHTS, ACTION_OUTCOME_WEIGHTS, PAYMENT_TYPE_WEIGHTS,
    # behavioural
    BEHAVIOURAL_RESPONSE_RATES, BEHAVIOURAL_AVG_DAYS_TO_RESPOND,
    BEHAVIOURAL_SELF_CURE_PROBS, BEHAVIOURAL_CALL_PICKUP_RATES,
    BEHAVIOURAL_ESCALATION_RATES,
    # communication
    COMMUNICATION_CHANNELS, COMMUNICATION_TIME_WINDOWS, COMMUNICATION_LANGUAGES,
    COMMUNICATION_WHATSAPP_OPTIN_RATES, COMMUNICATION_DND_RATES,
    COMMUNICATION_EMAIL_DELIVERABLE_RATES, COMMUNICATION_CHANNEL_WEIGHTS,
    # collateral
    COLLATERAL_BY_LOAN_TYPE, COLLATERAL_LTV_RANGES,
    COLLATERAL_CONDITION_WEIGHTS_BY_TIER, COLLATERAL_FORCED_SALE_HAIRCUT,
    COLLATERAL_ENCUMBRANCE_RATES,
)

_faker = Faker("en_IN")


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _weighted_choice(weights: dict, rng: random.Random) -> str:
    """Choose a key from a dict of {key: weight} using the given RNG."""
    keys = list(weights.keys())
    vals = list(weights.values())
    return rng.choices(keys, weights=vals, k=1)[0]


def _dpd_from_bucket(bucket_key: str, rng: random.Random) -> int:
    """Sample an integer DPD value consistent with the given bucket key."""
    _, lo, hi = DPD_BUCKETS[bucket_key]
    if lo == hi:
        return lo
    return rng.randint(lo, hi)


def _outstanding_for(segment: str, risk_tier: str, rng: random.Random) -> float:
    """Sample outstanding amount (INR) for the given segment/tier."""
    key = (segment, risk_tier)
    if key not in OUTSTANDING_RANGES:
        key = (segment, "any")
    lo, hi = OUTSTANDING_RANGES[key]
    return round(rng.uniform(lo, hi), -2)   # round to nearest 100


def _generate_payment_history(risk_tier: str, rng: random.Random) -> str:
    """Generate a 12-character Markov chain payment sequence."""
    init = MARKOV_INIT[risk_tier]
    states = list(init.keys())
    probs  = list(init.values())
    state  = rng.choices(states, weights=probs, k=1)[0]

    sequence = [state]
    matrix   = MARKOV_MATRICES[risk_tier]
    for _ in range(11):
        transitions = matrix[state]
        state = rng.choices(list(transitions.keys()), weights=list(transitions.values()), k=1)[0]
        sequence.append(state)
    return "".join(sequence)


def _bucket_label(bucket_key: str) -> str:
    return DPD_BUCKETS[bucket_key][0]


def _compute_target(
    risk_tier: str,
    dpd_bucket: str,
    promise_to_pay: bool,
    contact_attempts: int,
    resolution_status: str,
    payment_history: str,
    rng: random.Random,
    balance_scalar: float = 1.0,
) -> int:
    """Compute target_paid_30d probabilistically. See Appendix F."""
    # HARD overrides first
    if resolution_status == "Written-off":
        return 0
    if payment_history.count("P") == 0:
        return 0

    p = BASE_PAID_PROB[risk_tier][dpd_bucket] * balance_scalar

    # Modifiers (Appendix F.2)
    if promise_to_pay:
        p += 0.18
    elif payment_history[-3:].count("M") >= 2:
        p -= 0.08

    if contact_attempts >= 10:
        p += 0.06
    elif contact_attempts == 0:
        p -= 0.10

    if resolution_status == "PTP":
        p += 0.12
    elif resolution_status == "Legal":
        p -= 0.15

    if payment_history[-3:] == "PPP":
        p += 0.10
    elif payment_history[-3:] == "MMM":
        p -= 0.15

    p = max(0.02, min(0.97, p))
    return int(rng.random() < p)


def _generate_bureau_fields(dpd_bucket: str, rng: random.Random) -> dict:
    """Generate bureau score fields correlated with dpd_bucket (Appendix E.1)."""
    lo, mode, hi = CIBIL_RANGES[dpd_bucket]
    cibil = int(rng.triangular(lo, hi, mode))  # Python random.triangular order: low, high, mode
    if dpd_bucket == "npa":
        cibil = min(cibil, 529)  # enforce NPA CIBIL hard cap (hi in CIBIL_RANGES["npa"] is 530)
    cibil = max(300, min(900, cibil))

    bucket_to_enq_range = {
        "current": (0, 2), "early": (1, 5),
        "mild": (3, 10), "severe": (3, 10), "npa": (5, 15),
    }
    enq_lo, enq_hi = bucket_to_enq_range.get(dpd_bucket, (1, 5))

    return {
        "cibil_score": cibil,
        "internal_score": max(0, cibil - rng.randint(0, 50)),
        "bureau_enquiries_6m": rng.randint(enq_lo, enq_hi),
    }


def _generate_demographic_fields(rng: random.Random) -> dict:
    """Generate demographic fields using Faker hi_IN locale."""
    city_tier = rng.choices(
        ["Metro", "Tier-1", "Tier-2", "Rural"],
        weights=[40, 30, 20, 10], k=1
    )[0]
    income_bands = ["Low", "Mid", "High", "Very High"]
    return {
        "name":          _faker.name(),
        "age":           rng.randint(22, 65),
        "city":          _faker.city(),
        "state":         _faker.state(),
        "city_tier":     city_tier,
        "income_band":   rng.choices(income_bands, weights=[25, 40, 25, 10], k=1)[0],
        "employer_type": rng.choice(["Salaried", "Self-Employed", "Business", "Agriculture"]),
    }


def _generate_action_history(
    dpd_bucket: str,
    risk_tier: str,
    resolution_status: str,
    rng: random.Random,
) -> list[dict]:
    """Generate a list of collection actions taken post-call."""
    lo, hi = ACTION_COUNT_RANGES[dpd_bucket]
    n_actions = rng.randint(lo, hi)

    # Build action type pool — exclude zero-weight actions
    type_weights = ACTION_TYPE_WEIGHTS[dpd_bucket]
    valid_actions = [a for a in ACTION_TYPES if type_weights[a] > 0]
    valid_action_weights = [type_weights[a] for a in valid_actions]

    # Build outcome pool — Written-off must never produce PAYMENT
    outcome_weights_raw = ACTION_OUTCOME_WEIGHTS[risk_tier]
    if resolution_status == "Written-off":
        outcome_pool = {k: v for k, v in outcome_weights_raw.items() if k != "PAYMENT"}
    else:
        outcome_pool = outcome_weights_raw

    outcome_keys = list(outcome_pool.keys())
    outcome_vals = list(outcome_pool.values())

    # Sample n_actions distinct days from 1-28, sorted ascending
    day_pool = sorted(rng.sample(range(1, 29), n_actions))

    # Generate raw actions
    actions = []
    for seq in range(1, n_actions + 1):
        action = rng.choices(valid_actions, weights=valid_action_weights, k=1)[0]
        outcome = rng.choices(outcome_keys, weights=outcome_vals, k=1)[0]
        actions.append({
            "seq":             seq,
            "action":          action,
            "channel":         ACTION_CHANNEL_MAP[action],
            "outcome":         outcome,
            "days_since_call": day_pool[seq - 1],
        })

    # Consistency overrides on the last entry
    last = actions[-1]

    if resolution_status == "PTP" and not any(e["outcome"] == "PTP" for e in actions):
        last["outcome"] = "PTP"

    if resolution_status == "Settled":
        last["outcome"] = "SETTLED"

    if resolution_status == "Legal" and not any(e["action"] == "LEGAL_NOTICE" for e in actions):
        last["action"] = "LEGAL_NOTICE"
        last["channel"] = ACTION_CHANNEL_MAP["LEGAL_NOTICE"]
        last["outcome"] = "NO_RESPONSE"

    return actions


def _generate_payment_history_post_call(
    target_paid_30d: int,
    resolution_status: str,
    emi_amount: float,
    risk_tier: str,
    rng: random.Random,
) -> list[dict]:
    """Generate post-call payment events. Empty when not paid or written-off."""
    if target_paid_30d == 0 or resolution_status == "Written-off":
        return []

    n_payments = rng.randint(1, 3)
    type_weights = PAYMENT_TYPE_WEIGHTS[risk_tier]
    ptype_keys = list(type_weights.keys())
    ptype_vals = list(type_weights.values())

    # Sample n_payments distinct days from 1-30, sorted ascending
    day_pool = sorted(rng.sample(range(1, 31), n_payments))

    payments = []
    for seq in range(1, n_payments + 1):
        payment_type = rng.choices(ptype_keys, weights=ptype_vals, k=1)[0]

        if payment_type == "FULL":
            amount = emi_amount
        elif payment_type == "PARTIAL":
            amount = round(emi_amount * rng.uniform(0.30, 0.79), -2)
        else:  # MINIMUM
            amount = round(emi_amount * rng.uniform(0.10, 0.29), -2)
        amount = max(amount, 100.0)

        channel = rng.choices(PAYMENT_CHANNELS, weights=PAYMENT_CHANNEL_WEIGHTS, k=1)[0]

        payments.append({
            "seq":             seq,
            "days_after_call": day_pool[seq - 1],
            "amount_paid":     amount,
            "payment_type":    payment_type,
            "channel":         channel,
        })

    return payments


# ---------------------------------------------------------------------------
# Behavioural module
# ---------------------------------------------------------------------------

def _generate_behavioural_fields(risk_tier: str, dpd_bucket: str, rng: random.Random) -> dict:
    """Generate behavioural scoring fields correlated with risk tier and DPD bucket."""
    rr_lo, rr_hi = BEHAVIOURAL_RESPONSE_RATES[risk_tier]
    response_rate = round(rng.uniform(rr_lo, rr_hi), 4)

    dr_lo, dr_hi = BEHAVIOURAL_AVG_DAYS_TO_RESPOND[risk_tier]
    avg_days_to_respond = round(rng.uniform(dr_lo, dr_hi), 2)

    sc_lo, sc_hi = BEHAVIOURAL_SELF_CURE_PROBS.get(
        (dpd_bucket, risk_tier),
        BEHAVIOURAL_SELF_CURE_PROBS.get(("npa", "npa"), (0.00, 0.02)),
    )
    self_cure_probability = round(rng.uniform(sc_lo, sc_hi), 4)

    pu_lo, pu_hi = BEHAVIOURAL_CALL_PICKUP_RATES[risk_tier]
    call_pickup_rate = round(rng.uniform(pu_lo, pu_hi), 4)

    escalation_flag = rng.random() < BEHAVIOURAL_ESCALATION_RATES[dpd_bucket]

    return {
        "response_rate":        response_rate,
        "avg_days_to_respond":  avg_days_to_respond,
        "self_cure_probability": self_cure_probability,
        "call_pickup_rate":     call_pickup_rate,
        "escalation_flag":      escalation_flag,
    }


# ---------------------------------------------------------------------------
# Communication module
# ---------------------------------------------------------------------------

def _generate_communication_fields(risk_tier: str, city_tier: str, rng: random.Random) -> dict:
    """Generate contact channel preference and reachability fields."""
    channel_weights = COMMUNICATION_CHANNEL_WEIGHTS[risk_tier]
    preferred_channel = rng.choices(
        list(channel_weights.keys()), weights=list(channel_weights.values()), k=1
    )[0]

    contact_time_window = rng.choice(COMMUNICATION_TIME_WINDOWS)
    language_preference = rng.choice(COMMUNICATION_LANGUAGES)

    whatsapp_rate = COMMUNICATION_WHATSAPP_OPTIN_RATES.get(city_tier, 0.40)
    whatsapp_opted_in = rng.random() < whatsapp_rate

    dnd_rate = COMMUNICATION_DND_RATES[risk_tier]
    do_not_disturb = rng.random() < dnd_rate

    email_rate = COMMUNICATION_EMAIL_DELIVERABLE_RATES[risk_tier]
    email_deliverable = rng.random() < email_rate

    return {
        "preferred_channel":    preferred_channel,
        "contact_time_window":  contact_time_window,
        "language_preference":  language_preference,
        "whatsapp_opted_in":    whatsapp_opted_in,
        "do_not_disturb":       do_not_disturb,
        "email_deliverable":    email_deliverable,
    }


# ---------------------------------------------------------------------------
# Collateral module
# ---------------------------------------------------------------------------

def _generate_collateral_fields(
    loan_type: str,
    outstanding_amount: float,
    risk_tier: str,
    rng: random.Random,
) -> dict:
    """Generate collateral / security asset fields for the loan."""
    collateral_type = COLLATERAL_BY_LOAN_TYPE.get(loan_type, "Unsecured")

    if collateral_type == "Unsecured":
        return {
            "collateral_type":    collateral_type,
            "collateral_value":   0.0,
            "ltv_ratio":          0.0,
            "collateral_condition": "N/A",
            "encumbrance_status": False,
            "forced_sale_value":  0.0,
        }

    ltv_lo, ltv_hi = COLLATERAL_LTV_RANGES[risk_tier]
    ltv_ratio = round(rng.uniform(ltv_lo, ltv_hi), 4)

    # Derive collateral value from outstanding and LTV (avoid division by zero)
    collateral_value = round(outstanding_amount / max(ltv_ratio, 0.01), 2)

    haircut_lo, haircut_hi = COLLATERAL_FORCED_SALE_HAIRCUT
    forced_sale_value = round(collateral_value * rng.uniform(haircut_lo, haircut_hi), 2)

    condition_weights = COLLATERAL_CONDITION_WEIGHTS_BY_TIER[risk_tier]
    collateral_condition = rng.choices(
        list(condition_weights.keys()), weights=list(condition_weights.values()), k=1
    )[0]

    encumbrance_rate = COLLATERAL_ENCUMBRANCE_RATES[risk_tier]
    encumbrance_status = rng.random() < encumbrance_rate

    return {
        "collateral_type":      collateral_type,
        "collateral_value":     collateral_value,
        "ltv_ratio":            ltv_ratio,
        "collateral_condition": collateral_condition,
        "encumbrance_status":   encumbrance_status,
        "forced_sale_value":    forced_sale_value,
    }


# ---------------------------------------------------------------------------
# Core record generation
# ---------------------------------------------------------------------------

def generate_record(
    rng: random.Random | None = None,
    segment: str | None = None,
    risk_tier: str | None = None,
    dpd_bucket: str | None = None,
    schema_modules: list | None = None,
    balance_scalar: float = 1.0,
    dpd_weights: dict | None = None,
    segment_weights: dict | None = None,
) -> dict:
    """Generate a single synthetic collections record with core fields."""
    if rng is None:
        rng = random.Random()

    _dpd_weights = dpd_weights or DEFAULT_DPD_WEIGHTS
    _seg_weights = segment_weights or DEFAULT_SEGMENT_WEIGHTS

    segment    = segment   or _weighted_choice(_seg_weights, rng)
    risk_tier  = risk_tier or _weighted_choice(DEFAULT_RISK_WEIGHTS[segment], rng)
    dpd_bucket = dpd_bucket or _weighted_choice(_dpd_weights, rng)

    dpd              = _dpd_from_bucket(dpd_bucket, rng)
    outstanding      = _outstanding_for(segment, risk_tier, rng)
    # EMI is a fraction of outstanding (2%–12%), always strictly less than outstanding.
    # Even at maximum 12% of the minimum outstanding (10,000 INR = 1,200 INR), EMI < outstanding.
    emi_fraction     = rng.uniform(0.02, 0.12)
    emi_amount       = round(outstanding * emi_fraction, -2)
    # Guard: ensure EMI is strictly less than outstanding after rounding.
    # (Rounding to -2 could theoretically equal outstanding for very small values.)
    if emi_amount >= outstanding:
        emi_amount = outstanding - 100
    payment_history  = _generate_payment_history(risk_tier, rng)
    contact_attempts = rng.randint(*CONTACT_ATTEMPTS_RANGES[dpd_bucket])
    resolution_status = _weighted_choice(RESOLUTION_DIST[dpd_bucket], rng)
    promise_to_pay   = contact_attempts > 0 and rng.random() < 0.40

    target_paid_30d = _compute_target(
        risk_tier, dpd_bucket, promise_to_pay,
        contact_attempts, resolution_status, payment_history, rng,
        balance_scalar=balance_scalar,
    )

    # Use rng-based customer_id (not uuid4) so seeded RNG produces reproducible IDs.
    customer_id = f"CUST{rng.randint(100_000_000, 999_999_999)}"

    record = {
        "customer_id":         customer_id,
        "account_id":          f"ACC{rng.randint(1_000_000, 9_999_999)}",
        "loan_type":           rng.choice(LOAN_TYPES),
        "segment":             segment,
        "risk_tier":           risk_tier,
        "outstanding_amount":  outstanding,
        "emi_amount":          emi_amount,
        "dpd":                 dpd,
        "dpd_bucket":          _bucket_label(dpd_bucket),
        "payment_history_12m": payment_history,
        "contact_attempts":    contact_attempts,
        "promise_to_pay":      promise_to_pay,
        "resolution_status":   resolution_status,
        "target_paid_30d":     target_paid_30d,
    }

    # Optional schema modules
    schema_modules = schema_modules or []
    if "demographic" in schema_modules:
        record.update(_generate_demographic_fields(rng))
    if "bureau" in schema_modules:
        record.update(_generate_bureau_fields(dpd_bucket, rng))
    if "interactions" in schema_modules:
        record["action_history"] = _generate_action_history(
            dpd_bucket, risk_tier, resolution_status, rng
        )
        record["payment_history"] = _generate_payment_history_post_call(
            target_paid_30d, resolution_status, emi_amount, risk_tier, rng
        )
    if "behavioural" in schema_modules:
        record.update(_generate_behavioural_fields(risk_tier, dpd_bucket, rng))
    if "communication" in schema_modules:
        # Use city_tier from record if demographic module already ran, else sample one
        _city_tier = record.get("city_tier") or rng.choices(
            ["Metro", "Tier-1", "Tier-2", "Rural"], weights=[40, 30, 20, 10], k=1
        )[0]
        record.update(_generate_communication_fields(risk_tier, _city_tier, rng))
    if "collateral" in schema_modules:
        record.update(_generate_collateral_fields(
            record["loan_type"], outstanding, risk_tier, rng
        ))
    if "next_action" in schema_modules:
        result = suggested_next_action(record)
        record["suggested_next_action"]  = result["next_action"]
        record["next_action_channel"]    = result["channel"]
        record["next_action_reason"]     = result["reason"]
        record["next_action_priority"]   = result["priority"]
        record["next_action_confidence"] = result["confidence"]

    return record


# ---------------------------------------------------------------------------
# Dataset generation
# ---------------------------------------------------------------------------

def generate_dataset(
    n: int = 10_000,
    seed: int = 42,
    dpd_weights: dict | None = None,
    segment_weights: dict | None = None,
    class_balance_target: float = 0.80,
    schema_modules: list | None = None,
) -> pd.DataFrame:
    """Generate n synthetic records and return as a DataFrame.

    Note: class_balance_target calibration is based on default dpd_weights and
    segment_weights. Custom weight distributions will shift the actual paid rate
    away from the target; verify empirically if using non-default weights.
    """
    rng = random.Random(seed)
    np.random.seed(seed)

    # Calibration table mapping target paid rate → balance_scalar.
    # Built empirically against default weights (seed=42, n=10000) by probing
    # balance_scalar values in [0.4, 12.0] and recording resulting paid rates.
    # Regenerate if Markov matrices or BASE_PAID_PROB are modified.
    # np.interp requires strictly increasing x-values; duplicates have been removed.
    _cal_rates   = [0.34, 0.39, 0.44, 0.49, 0.53, 0.57, 0.61, 0.64, 0.66,
                    0.69, 0.71, 0.74, 0.76, 0.77, 0.78, 0.79, 0.80,
                    0.81, 0.82]
    _cal_scalars = [0.50, 0.60, 0.70, 0.80, 0.90, 1.00, 1.10, 1.20, 1.30,
                    1.50, 1.70, 2.00, 2.50, 3.00, 3.50, 4.00, 4.50,
                    6.00, 8.00]
    balance_scalar = float(np.interp(class_balance_target, _cal_rates, _cal_scalars))

    records = [
        generate_record(
            rng=rng,
            schema_modules=schema_modules or [],
            balance_scalar=balance_scalar,
            dpd_weights=dpd_weights,
            segment_weights=segment_weights,
        )
        for _ in range(n)
    ]
    return pd.DataFrame(records)
