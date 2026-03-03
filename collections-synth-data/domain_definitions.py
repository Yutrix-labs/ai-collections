"""
domain_definitions.py
Single source of truth for all collections domain constants.
Source: Fintaar_Collections_SynthData_PR_Plan_v2.docx, Appendices D & E.
"""

# --- State alphabet for payment_history_12m ---
STATE_CHARS = ["P", "D", "M", "-"]

# --- Risk tiers (ordered lowest to highest risk) ---
RISK_TIERS = ["prime", "near_prime", "sub_prime", "npa"]

# --- Customer segments ---
SEGMENTS = ["Retail", "SME", "Corporate", "MSME"]

# --- Loan types ---
LOAN_TYPES = ["Home", "Personal", "Auto", "MSME", "Gold", "Credit Card"]

# --- DPD bucket definitions ---
# (label, min_dpd, max_dpd) — weights are in DEFAULT_DPD_WEIGHTS
DPD_BUCKETS = {
    "current": ("Current",          0,   0),
    "early":   ("Early (1-30)",     1,  30),
    "mild":    ("Mild (31-60)",    31,  60),
    "severe":  ("Severe (61-90)", 61,  90),
    "npa":     ("NPA (90+)",       91, 365),
}

# --- Markov transition matrices (Appendix D) ---
# Structure: {from_state: {to_state: probability}}
MARKOV_MATRICES = {
    "prime": {
        "P": {"P": 0.92, "D": 0.06, "M": 0.01, "-": 0.01},
        "D": {"P": 0.75, "D": 0.18, "M": 0.06, "-": 0.01},
        "M": {"P": 0.50, "D": 0.30, "M": 0.18, "-": 0.02},
        "-": {"P": 0.00, "D": 0.00, "M": 0.00, "-": 1.00},
    },
    "near_prime": {
        "P": {"P": 0.78, "D": 0.15, "M": 0.06, "-": 0.01},
        "D": {"P": 0.55, "D": 0.28, "M": 0.15, "-": 0.02},
        "M": {"P": 0.30, "D": 0.35, "M": 0.32, "-": 0.03},
        "-": {"P": 0.00, "D": 0.00, "M": 0.00, "-": 1.00},
    },
    "sub_prime": {
        "P": {"P": 0.58, "D": 0.25, "M": 0.14, "-": 0.03},
        "D": {"P": 0.30, "D": 0.35, "M": 0.30, "-": 0.05},
        "M": {"P": 0.12, "D": 0.28, "M": 0.52, "-": 0.08},
        "-": {"P": 0.00, "D": 0.00, "M": 0.00, "-": 1.00},
    },
    "npa": {
        "P": {"P": 0.30, "D": 0.28, "M": 0.35, "-": 0.07},
        "D": {"P": 0.10, "D": 0.25, "M": 0.55, "-": 0.10},
        "M": {"P": 0.04, "D": 0.10, "M": 0.72, "-": 0.14},
        "-": {"P": 0.00, "D": 0.00, "M": 0.00, "-": 1.00},
    },
}

# --- Markov initialisation distributions (Appendix D.3) ---
MARKOV_INIT = {
    "prime":      {"P": 0.95, "D": 0.04, "M": 0.01, "-": 0.00},
    "near_prime": {"P": 0.80, "D": 0.15, "M": 0.05, "-": 0.00},
    "sub_prime":  {"P": 0.60, "D": 0.25, "M": 0.15, "-": 0.00},
    "npa":        {"P": 0.20, "D": 0.30, "M": 0.50, "-": 0.00},
}

# --- CIBIL ranges by DPD bucket (Appendix E.1) ---
# (low, mode, high) for triangular distribution
CIBIL_RANGES = {
    "current": (700, 780, 900),
    "early":   (620, 680, 750),
    "mild":    (550, 600, 680),
    "severe":  (450, 520, 600),
    "npa":     (300, 420, 530),
}

# --- Resolution status distribution by DPD bucket (Appendix E.3) ---
# Values are integer percentages summing to 100
RESOLUTION_DIST = {
    "current": {"Open": 70, "PTP": 20, "Partial": 8,  "Settled": 2,  "Legal": 0,  "Written-off": 0},
    "early":   {"Open": 45, "PTP": 35, "Partial": 12, "Settled": 5,  "Legal": 2,  "Written-off": 1},
    "mild":    {"Open": 25, "PTP": 30, "Partial": 20, "Settled": 15, "Legal": 7,  "Written-off": 3},
    "severe":  {"Open": 10, "PTP": 20, "Partial": 18, "Settled": 20, "Legal": 22, "Written-off": 10},
    "npa":     {"Open": 5,  "PTP": 10, "Partial": 8,  "Settled": 15, "Legal": 32, "Written-off": 30},
}

# --- Contact attempts ranges by DPD bucket (Appendix E.4) ---
CONTACT_ATTEMPTS_RANGES = {
    "current": (0, 2),
    "early":   (2, 6),
    "mild":    (5, 12),
    "severe":  (8, 18),
    "npa":     (10, 20),
}

# --- Outstanding amount ranges (INR) by segment x risk tier (Appendix E.2) ---
# Key: (segment, risk_tier) -> (min_inr, max_inr)
# Segments without tier-specific ranges use "any"
OUTSTANDING_RANGES = {
    ("Retail",    "prime"):      (50_000,     15_00_000),
    ("Retail",    "near_prime"): (30_000,     10_00_000),
    ("Retail",    "sub_prime"):  (10_000,      5_00_000),
    ("Retail",    "npa"):        (10_000,      3_00_000),
    ("SME",       "any"):        (5_00_000,  2_00_00_000),
    ("MSME",      "any"):        (1_00_000,   50_00_000),
    ("Corporate", "prime"):      (50_00_000, 5_00_00_000),
    ("Corporate", "near_prime"): (20_00_000, 2_00_00_000),
    ("Corporate", "sub_prime"):  (10_00_000, 1_00_00_000),
    ("Corporate", "npa"):        (10_00_000, 5_00_00_000),
}

# --- Base paid-30d probability table (Appendix F.1) ---
# [risk_tier][dpd_bucket] -> float
BASE_PAID_PROB = {
    "prime":      {"current": 0.90, "early": 0.75, "mild": 0.55, "severe": 0.30, "npa": 0.10},
    "near_prime": {"current": 0.80, "early": 0.60, "mild": 0.40, "severe": 0.20, "npa": 0.07},
    "sub_prime":  {"current": 0.65, "early": 0.42, "mild": 0.25, "severe": 0.12, "npa": 0.04},
    "npa":        {"current": 0.40, "early": 0.22, "mild": 0.12, "severe": 0.06, "npa": 0.02},
}

# --- DPD bucket weights (configurable defaults) ---
DEFAULT_DPD_WEIGHTS = {
    "current": 45,
    "early":   20,
    "mild":    15,
    "severe":  12,
    "npa":      8,
}

# --- Segment distribution defaults ---
DEFAULT_SEGMENT_WEIGHTS = {
    "Retail":    60,
    "SME":       20,
    "MSME":      15,
    "Corporate":  5,
}

# --- Risk tier distribution per segment ---
DEFAULT_RISK_WEIGHTS = {
    "Retail":    {"prime": 35, "near_prime": 30, "sub_prime": 25, "npa": 10},
    "SME":       {"prime": 25, "near_prime": 30, "sub_prime": 30, "npa": 15},
    "MSME":      {"prime": 20, "near_prime": 30, "sub_prime": 35, "npa": 15},
    "Corporate": {"prime": 40, "near_prime": 35, "sub_prime": 20, "npa":  5},
}

# ---------------------------------------------------------------------------
# --- Interactions module constants (action_history & payment_history) ---
# ---------------------------------------------------------------------------

# Action types (what the agent did)
ACTION_TYPES = ["CALL", "SMS", "EMAIL", "VISIT", "LEGAL_NOTICE"]

# Outcomes of each action
ACTION_OUTCOMES = ["PTP", "PAYMENT", "NO_RESPONSE", "CALLBACK", "DISPUTE", "SETTLED"]

# Channel mapped from action type (used to set channel field)
ACTION_CHANNEL_MAP = {
    "CALL":         "phone",
    "SMS":          "sms",
    "EMAIL":        "email",
    "VISIT":        "field",
    "LEGAL_NOTICE": "legal",
}

# Payment channels for post-call payment events
PAYMENT_CHANNELS = ["upi", "bank_transfer", "cash", "cheque", "auto_debit"]

# Weights for payment channels (same for all tiers)
PAYMENT_CHANNEL_WEIGHTS = [45, 25, 15, 10, 5]

# Payment types
PAYMENT_TYPES = ["FULL", "PARTIAL", "MINIMUM"]

# Number of action entries per record, by dpd_bucket
ACTION_COUNT_RANGES = {
    "current": (1, 2),
    "early":   (1, 3),
    "mild":    (2, 4),
    "severe":  (3, 5),
    "npa":     (3, 5),
}

# Action type weights by dpd_bucket
# Higher DPD → more escalated actions (VISIT, LEGAL_NOTICE)
ACTION_TYPE_WEIGHTS = {
    "current": {"CALL": 60, "SMS": 30, "EMAIL": 10, "VISIT": 0,  "LEGAL_NOTICE": 0},
    "early":   {"CALL": 55, "SMS": 30, "EMAIL": 15, "VISIT": 0,  "LEGAL_NOTICE": 0},
    "mild":    {"CALL": 50, "SMS": 25, "EMAIL": 20, "VISIT": 5,  "LEGAL_NOTICE": 0},
    "severe":  {"CALL": 40, "SMS": 20, "EMAIL": 15, "VISIT": 15, "LEGAL_NOTICE": 10},
    "npa":     {"CALL": 30, "SMS": 15, "EMAIL": 10, "VISIT": 20, "LEGAL_NOTICE": 25},
}

# Action outcome weights by risk_tier
# Prime customers more likely to PTP/pay; NPA more likely to not respond
ACTION_OUTCOME_WEIGHTS = {
    "prime":      {"PTP": 35, "PAYMENT": 25, "NO_RESPONSE": 20, "CALLBACK": 15, "DISPUTE": 4,  "SETTLED": 1},
    "near_prime": {"PTP": 30, "PAYMENT": 20, "NO_RESPONSE": 25, "CALLBACK": 15, "DISPUTE": 8,  "SETTLED": 2},
    "sub_prime":  {"PTP": 20, "PAYMENT": 15, "NO_RESPONSE": 35, "CALLBACK": 15, "DISPUTE": 13, "SETTLED": 2},
    "npa":        {"PTP": 10, "PAYMENT":  8, "NO_RESPONSE": 50, "CALLBACK": 12, "DISPUTE": 15, "SETTLED": 5},
}

# Post-call payment type weights by risk_tier
# Prime more likely to pay FULL; NPA more likely to pay PARTIAL or MINIMUM
PAYMENT_TYPE_WEIGHTS = {
    "prime":      {"FULL": 60, "PARTIAL": 30, "MINIMUM": 10},
    "near_prime": {"FULL": 45, "PARTIAL": 40, "MINIMUM": 15},
    "sub_prime":  {"FULL": 20, "PARTIAL": 50, "MINIMUM": 30},
    "npa":        {"FULL": 10, "PARTIAL": 45, "MINIMUM": 45},
}

# ---------------------------------------------------------------------------
# --- Behavioural module constants ---
# ---------------------------------------------------------------------------

# Response rate ranges (min, max) by risk_tier — float sampled uniformly
# Fraction of contact attempts that get a response
BEHAVIOURAL_RESPONSE_RATES = {
    "prime":      (0.65, 0.95),
    "near_prime": (0.45, 0.80),
    "sub_prime":  (0.25, 0.60),
    "npa":        (0.05, 0.35),
}

# Average days to respond ranges (min, max) by risk_tier
# Lower = faster response (prime responds quickly; NPA is slow or never)
BEHAVIOURAL_AVG_DAYS_TO_RESPOND = {
    "prime":      (0.5, 3.0),
    "near_prime": (1.0, 7.0),
    "sub_prime":  (3.0, 14.0),
    "npa":        (7.0, 28.0),
}

# Self-cure probability (min, max) by (dpd_bucket, risk_tier)
# Probability borrower pays without active agent outreach
BEHAVIOURAL_SELF_CURE_PROBS = {
    ("current", "prime"):      (0.50, 0.85),
    ("current", "near_prime"): (0.35, 0.70),
    ("current", "sub_prime"):  (0.15, 0.45),
    ("current", "npa"):        (0.05, 0.25),
    ("early",   "prime"):      (0.30, 0.65),
    ("early",   "near_prime"): (0.15, 0.45),
    ("early",   "sub_prime"):  (0.05, 0.25),
    ("early",   "npa"):        (0.02, 0.12),
    ("mild",    "prime"):      (0.10, 0.35),
    ("mild",    "near_prime"): (0.05, 0.20),
    ("mild",    "sub_prime"):  (0.02, 0.12),
    ("mild",    "npa"):        (0.01, 0.07),
    ("severe",  "prime"):      (0.05, 0.18),
    ("severe",  "near_prime"): (0.02, 0.10),
    ("severe",  "sub_prime"):  (0.01, 0.06),
    ("severe",  "npa"):        (0.00, 0.04),
    ("npa",     "prime"):      (0.02, 0.10),
    ("npa",     "near_prime"): (0.01, 0.06),
    ("npa",     "sub_prime"):  (0.00, 0.04),
    ("npa",     "npa"):        (0.00, 0.02),
}

# Call pickup rate ranges (min, max) by risk_tier
# Fraction of outbound calls that the borrower actually picks up
BEHAVIOURAL_CALL_PICKUP_RATES = {
    "prime":      (0.55, 0.90),
    "near_prime": (0.35, 0.70),
    "sub_prime":  (0.15, 0.50),
    "npa":        (0.03, 0.25),
}

# Escalation flag probability by dpd_bucket
# Probability that the account was escalated to a senior agent / legal team
BEHAVIOURAL_ESCALATION_RATES = {
    "current": 0.03,
    "early":   0.10,
    "mild":    0.25,
    "severe":  0.55,
    "npa":     0.80,
}

# ---------------------------------------------------------------------------
# --- Communication module constants ---
# ---------------------------------------------------------------------------

# Valid preferred contact channels
COMMUNICATION_CHANNELS = ["phone", "sms", "email", "whatsapp", "field"]

# Valid contact time windows
COMMUNICATION_TIME_WINDOWS = ["morning", "afternoon", "evening", "weekend"]

# Valid language preferences (Indian context)
COMMUNICATION_LANGUAGES = [
    "Hindi", "English", "Marathi", "Tamil", "Telugu",
    "Bengali", "Gujarati", "Kannada",
]

# WhatsApp opt-in rate by city_tier (higher in urban areas)
COMMUNICATION_WHATSAPP_OPTIN_RATES = {
    "Metro":  0.80,
    "Tier-1": 0.65,
    "Tier-2": 0.45,
    "Rural":  0.20,
}

# Do-Not-Disturb registration rate by risk_tier
# Distressed borrowers more likely to register DND to avoid collections contact
COMMUNICATION_DND_RATES = {
    "prime":      0.05,
    "near_prime": 0.10,
    "sub_prime":  0.18,
    "npa":        0.30,
}

# Email deliverability rate by risk_tier
# NPA / rural accounts more likely to have stale or missing email addresses
COMMUNICATION_EMAIL_DELIVERABLE_RATES = {
    "prime":      0.88,
    "near_prime": 0.75,
    "sub_prime":  0.55,
    "npa":        0.30,
}

# Preferred channel weights by risk_tier
# Prime prefer phone/email; NPA more reachable via sms/field if at all
COMMUNICATION_CHANNEL_WEIGHTS = {
    "prime":      {"phone": 50, "sms": 20, "email": 20, "whatsapp": 8,  "field": 2},
    "near_prime": {"phone": 45, "sms": 25, "email": 15, "whatsapp": 12, "field": 3},
    "sub_prime":  {"phone": 35, "sms": 30, "email": 10, "whatsapp": 15, "field": 10},
    "npa":        {"phone": 25, "sms": 30, "email": 5,  "whatsapp": 15, "field": 25},
}

# ---------------------------------------------------------------------------
# --- Collateral module constants ---
# ---------------------------------------------------------------------------

# Maps loan_type → collateral_type
# Personal and Credit Card are unsecured (no collateral)
COLLATERAL_BY_LOAN_TYPE = {
    "Home":        "Property",
    "Auto":        "Vehicle",
    "Gold":        "Gold",
    "MSME":        "Machinery",
    "Personal":    "Unsecured",
    "Credit Card": "Unsecured",
}

# LTV ratio ranges (min, max) by risk_tier
# Higher risk → higher LTV (outstanding is high relative to collateral value)
COLLATERAL_LTV_RANGES = {
    "prime":      (0.30, 0.65),
    "near_prime": (0.50, 0.80),
    "sub_prime":  (0.65, 0.95),
    "npa":        (0.80, 1.20),   # can exceed 1.0 (underwater)
}

# Collateral condition weights by risk_tier
# Prime → mostly Good; NPA → skews Poor
COLLATERAL_CONDITION_WEIGHTS = {
    "Good": None,   # sentinel — actual weights set per tier below
    "Fair": None,
    "Poor": None,
}

COLLATERAL_CONDITION_WEIGHTS_BY_TIER = {
    "prime":      {"Good": 70, "Fair": 25, "Poor":  5},
    "near_prime": {"Good": 50, "Fair": 35, "Poor": 15},
    "sub_prime":  {"Good": 25, "Fair": 45, "Poor": 30},
    "npa":        {"Good": 10, "Fair": 35, "Poor": 55},
}

# Forced sale value haircut range (multiplier applied to collateral_value)
# Represents forced liquidation discount — typically 55-75% of market value
COLLATERAL_FORCED_SALE_HAIRCUT = (0.55, 0.75)

# Encumbrance rate by risk_tier
# Probability that collateral has another lien on it
COLLATERAL_ENCUMBRANCE_RATES = {
    "prime":      0.08,
    "near_prime": 0.15,
    "sub_prime":  0.25,
    "npa":        0.40,
}

# ---------------------------------------------------------------------------
# --- Next Action Engine constants ---
# ---------------------------------------------------------------------------

# Ordered list of valid next action strings
NEXT_ACTIONS = [
    "MONITOR",
    "SEND_SMS",
    "SEND_WHATSAPP",
    "SEND_EMAIL",
    "CALL_BACK",
    "FIELD_VISIT",
    "SEND_LEGAL_NOTICE",
    "OFFER_SETTLEMENT",
    "CLOSE_ACCOUNT",
]

# Maps next action → default channel string (None = no outbound channel)
ACTION_TO_CHANNEL = {
    "MONITOR":           None,
    "SEND_SMS":          "sms",
    "SEND_WHATSAPP":     "whatsapp",
    "SEND_EMAIL":        "email",
    "CALL_BACK":         "phone",
    "FIELD_VISIT":       "field",
    "SEND_LEGAL_NOTICE": "legal",
    "OFFER_SETTLEMENT":  "phone",
    "CLOSE_ACCOUNT":     None,
}

# DPD bucket → severity integer 0 (current) to 4 (NPA)
DPD_SEVERITY_SCORE = {
    "current": 0,
    "early":   1,
    "mild":    2,
    "severe":  3,
    "npa":     4,
}

# Per-action weight vectors for each signal group.
# Order: [paid_prob, dpd_severity, payment_history, response_signal,
#          channel_availability, recovery_potential]
# Values represent how much each signal ADDS to that action's score.
# Design: rows sum roughly to 1.0 — exact normalisation happens in engine.
ACTION_SIGNAL_WEIGHTS = {
    #                          paid  dpd   hist  resp  chan  recov
    "MONITOR":           [0.40, 0.00, 0.30, 0.20, 0.05, 0.05],
    "SEND_SMS":          [0.25, 0.10, 0.20, 0.25, 0.15, 0.05],
    "SEND_WHATSAPP":     [0.20, 0.10, 0.20, 0.20, 0.25, 0.05],
    "SEND_EMAIL":        [0.20, 0.10, 0.20, 0.20, 0.25, 0.05],
    "CALL_BACK":         [0.20, 0.15, 0.20, 0.25, 0.10, 0.10],
    "FIELD_VISIT":       [0.05, 0.30, 0.15, 0.20, 0.10, 0.20],
    "SEND_LEGAL_NOTICE": [0.05, 0.35, 0.20, 0.20, 0.05, 0.15],
    "OFFER_SETTLEMENT":  [0.10, 0.20, 0.15, 0.15, 0.10, 0.30],
    "CLOSE_ACCOUNT":     [0.50, 0.00, 0.20, 0.10, 0.05, 0.15],
}

# Priority thresholds (gap between top and second-best score)
PRIORITY_THRESHOLDS = {
    "HIGH":   0.70,
    "MEDIUM": 0.50,
}
