"""Central configuration: paths, target definition, feature lists, generation params.

Everything that the generator, trainer, and serving layer must agree on lives here so
the three stages can never drift apart.
"""

from __future__ import annotations

from pathlib import Path

# --------------------------------------------------------------------------- #
# Paths
# --------------------------------------------------------------------------- #
PKG_DIR = Path(__file__).resolve().parent
PROJECT_DIR = PKG_DIR.parent.parent                     # backend/ml-ptp
REPO_ROOT = PROJECT_DIR.parent.parent                   # ai-collections repo root

DATA_DIR = PROJECT_DIR / "data"
MODELS_DIR = PROJECT_DIR / "models"

# Source distribution sample shipped with the repo (used to bootstrap realistic features).
SOURCE_XLSX = REPO_ROOT / "Data_distribution.xlsx"
SOURCE_SHEET = "data"

# Generated training dataset.
TRAINING_CSV = DATA_DIR / "ptp_training_data.csv"

# Trained artifacts.
MODEL_PATH = MODELS_DIR / "ptp_model.joblib"
METADATA_PATH = MODELS_DIR / "model_metadata.json"

# Payment-probability models (LightGBM, 15d/30d).
# Bundled artifact from the ptp_prob_lightgbm notebook: a dict with p15/p30 regressors,
# per-column LabelEncoders, and classifier heads. Only p15/p30 are used here (the 15d/30d
# payment probabilities); the action/priority/confidence heads are intentionally not served.
PAYMENT_MODELS_DIR = MODELS_DIR / "payment"
PAYMENT_BUNDLE_PATH = PAYMENT_MODELS_DIR / "collections_models_v1.pkl"

RANDOM_SEED = 42

# --------------------------------------------------------------------------- #
# Likelihood bands (shared by PTP fulfillment + payment probabilities, UI-wide)
# --------------------------------------------------------------------------- #
# High >= 0.90 (green), Medium >= 0.70 (amber), Low < 0.70 (red).
BAND_HIGH_MIN = 0.90
BAND_MEDIUM_MIN = 0.70


def likelihood_band(probability: float | None) -> str:
    """Map a probability to its display band. Used for PTP and payment scores alike."""
    if probability is None:
        return "Unknown"
    if probability >= BAND_HIGH_MIN:
        return "High"
    if probability >= BAND_MEDIUM_MIN:
        return "Medium"
    return "Low"

# --------------------------------------------------------------------------- #
# Target definition  (decision: binary classifier, train on PTP-given accounts)
# --------------------------------------------------------------------------- #
# A PTP is considered "fulfilled" when at least half of the promised amount was kept.
PTP_KEPT_THRESHOLD = 0.5
TARGET_COL = "ptp_fulfilled"          # engineered binary label
RAW_TARGET_COL = "ptp_kept"           # continuous source from which the label is derived

# --------------------------------------------------------------------------- #
# Synthetic-data generation config  (mirrors the user's data-generation spec)
# --------------------------------------------------------------------------- #
# Section 7 — PROMISE-TO-PAY (PTP). These are the relationships that give the
# targets genuine, learnable signal tied to observable features.
GEN_CONFIG = {
    # ptp_given: Bernoulli, base rate lifted by how responsive the customer is.
    "ptp_given": {
        "base_p": 0.35,
        "response_uplift": 0.30,      # p = base_p + response_uplift * response_rate
    },
    # ptp_kept: Beta(2,3) fraction of promises kept, blended toward the customer's
    # historical paid-ratio (reliable payers keep promises). 0 when no PTP given.
    "ptp_kept": {
        "beta_alpha": 2,
        "beta_beta": 3,
        "paid_ratio_uplift": 0.30,    # convex blend weight on paid_ratio
        "zero_when_no_ptp": True,
        # Secondary realism effects (documented enhancement beyond the base spec):
        # heavy delinquency and weak credit modestly erode the kept fraction.
        "dpd_penalty": 0.0010,        # subtract dpd_penalty * latest_dpd
        "low_cibil_penalty": 0.10,    # subtract when cibil < 600 (and known)
    },
    # broken_ptp_count: Negative Binomial, mean scales with unkept * given.
    "broken_ptp_count": {
        "r": 1.5,
        "mu_base": 0.8,
        "mu_per_unkept": 3.0,         # mu = (mu_base + mu_per_unkept*(1-kept)) * given
        "max": 8,
    },
}

# --------------------------------------------------------------------------- #
# Feature schema for the model
# --------------------------------------------------------------------------- #
# Leakage / non-feature columns deliberately excluded from the model:
#   ptp_kept             -> the target is derived from it
#   self_cure_probability-> a derived model score (target leakage)
#   paid_after_days      -> post-outcome information (leakage)
#   ptp_given            -> constant after filtering to PTP-given accounts
#   account_id           -> identifier
#   action_history / payment_history -> raw strings, parsed into engineered features
EXCLUDED_COLS = {
    "account_id",
    "ptp_kept",
    "ptp_given",
    "self_cure_probability",
    "paid_after_days",
    "action_history",
    "payment_history",
}

CATEGORICAL_FEATURES = [
    "segment",
    "loan_type",
    "age_group",
    "income_band",
    "employer_type",
    "city_tier",
    "last_contact_channel",
    "preferred_channel",
    "language_preference",
    "best_time_to_call",
    "collateral_type",
    "payment_recent_status",   # engineered: last char of payment_history (P/M/R)
    "action_last",             # engineered: last channel in action_history
]

NUMERIC_FEATURES = [
    "latest_dpd",
    "dpd_bucket_0_30",
    "dpd_bucket_30_60",
    "dpd_bucket_60_90",
    "dpd_bucket_90_120",
    "npa_flag",
    "loan_amount",
    "outstanding_amount",
    "cibil_score",
    "internal_score",
    "bureau_enquiries_6m",
    "active_loans",
    "credit_utilization_pct",
    "total_interactions",
    "days_since_last_contact",
    "response_rate",
    "call_pickup_rate",
    "broken_ptp_count",
    "avg_days_to_pay",
    "escalation_flag",
    "whatsapp_opted_in",
    "do_not_disturb",
    "ltv_ratio",
    "forced_sale_value",
    # Engineered numeric features:
    "outstanding_ratio",       # outstanding_amount / loan_amount
    "is_secured",              # collateral present
    "pay_paid_ratio",          # share of 'P' in payment_history
    "pay_missed_ratio",        # share of 'M'
    "pay_returned_ratio",      # share of 'R'
    "action_count",            # number of actions in action_history
    "action_call_ratio",       # share of Call actions
    "action_field_ratio",      # share of Field Visit actions
]

ALL_FEATURES = NUMERIC_FEATURES + CATEGORICAL_FEATURES

# Human-readable labels for the explainability factors surfaced to the UI.
FEATURE_LABELS = {
    "pay_paid_ratio": "Historical on-time payment ratio",
    "pay_missed_ratio": "Historical missed-payment ratio",
    "response_rate": "Contact response rate",
    "call_pickup_rate": "Call pickup rate",
    "broken_ptp_count": "Past broken promises",
    "latest_dpd": "Days past due",
    "cibil_score": "Credit bureau score",
    "internal_score": "Internal risk score",
    "credit_utilization_pct": "Credit utilization",
    "outstanding_ratio": "Outstanding vs original loan",
    "escalation_flag": "Escalated account",
    "npa_flag": "NPA flag",
    "avg_days_to_pay": "Average days to pay",
    "total_interactions": "Total interactions",
    "days_since_last_contact": "Days since last contact",
}
