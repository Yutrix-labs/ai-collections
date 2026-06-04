"""Feature engineering shared by training and serving.

`engineer_features` is the single source of truth for turning raw account fields
(as they arrive from the backend / live data) into the model's feature matrix. The
training pipeline and the FastAPI service both call it, so they can never drift.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from . import config


def _clean_placeholders(df: pd.DataFrame) -> pd.DataFrame:
    """Convert known sentinel values into proper missing values.

    The source data encodes "unknown" with sentinels that would otherwise poison a
    numeric model:
      * cibil_score == 0      -> missing (valid CIBIL is 300-900)
      * paid_after_days == -1 -> "never paid" (column is excluded anyway, handled defensively)
      * ltv_ratio == 2.0 on unsecured loans -> placeholder, not a real LTV
    """
    df = df.copy()

    if "cibil_score" in df:
        df["cibil_score"] = df["cibil_score"].where(df["cibil_score"] > 0, np.nan)

    # ltv_ratio is a placeholder (2.0) wherever there is no collateral; treat as missing.
    if "ltv_ratio" in df and "collateral_type" in df:
        unsecured = df["collateral_type"].isna() | (df["collateral_type"].astype(str).str.lower() == "none")
        df.loc[unsecured & (df["ltv_ratio"] >= 2.0), "ltv_ratio"] = np.nan

    return df


def _parse_payment_history(s: pd.Series) -> pd.DataFrame:
    """Parse the 6-char P/M/R payment-history string into ratio features.

    P = paid, M = missed, R = returned/rolled. Reliable payers (high P ratio) are the
    primary driver of PTP fulfillment, so these ratios carry most of the signal.
    """
    s = s.fillna("").astype(str)
    length = s.str.len().replace(0, np.nan)
    out = pd.DataFrame(index=s.index)
    out["pay_paid_ratio"] = s.str.count("P") / length
    out["pay_missed_ratio"] = s.str.count("M") / length
    out["pay_returned_ratio"] = s.str.count("R") / length
    # Most recent payment status (last char) as a categorical signal.
    out["payment_recent_status"] = s.str[-1].replace("", np.nan)
    return out


def _parse_action_history(s: pd.Series) -> pd.DataFrame:
    """Parse the 'Call -> WhatsApp -> Visit' action sequence into count/ratio features."""
    s = s.fillna("").astype(str)
    out = pd.DataFrame(index=s.index)

    tokens = s.apply(lambda v: [t.strip() for t in v.split("->") if t.strip()] if v else [])
    counts = tokens.apply(len)
    out["action_count"] = counts

    def _ratio(token_match) -> pd.Series:
        return tokens.apply(
            lambda lst: (sum(1 for t in lst if token_match(t)) / len(lst)) if lst else np.nan
        )

    out["action_call_ratio"] = _ratio(lambda t: t.lower() in ("call", "voice call"))
    out["action_field_ratio"] = _ratio(lambda t: "visit" in t.lower())
    out["action_last"] = tokens.apply(lambda lst: lst[-1] if lst else np.nan)
    return out


def engineer_features(df: pd.DataFrame) -> pd.DataFrame:
    """Return a DataFrame containing exactly `config.ALL_FEATURES`, ready for the pipeline.

    Accepts a raw DataFrame with the source schema (extra columns are ignored, and any
    columns missing from the input are created as NaN so single-record scoring is robust).
    """
    df = _clean_placeholders(df)

    engineered = pd.DataFrame(index=df.index)

    # Derived numeric features.
    loan = df.get("loan_amount")
    outstanding = df.get("outstanding_amount")
    if loan is not None and outstanding is not None:
        engineered["outstanding_ratio"] = outstanding / loan.replace(0, np.nan)

    if "collateral_type" in df:
        collateral = df["collateral_type"]
        engineered["is_secured"] = (~(collateral.isna() | (collateral.astype(str).str.lower() == "none"))).astype(int)

    # History-derived features.
    if "payment_history" in df:
        engineered = engineered.join(_parse_payment_history(df["payment_history"]))
    if "action_history" in df:
        engineered = engineered.join(_parse_action_history(df["action_history"]))

    # Pass-through raw features that are used as-is.
    passthrough = [c for c in config.ALL_FEATURES if c not in engineered.columns]
    for col in passthrough:
        engineered[col] = df[col] if col in df.columns else np.nan

    # Normalise collateral_type missing -> explicit "None" category for the encoder.
    if "collateral_type" in engineered:
        engineered["collateral_type"] = engineered["collateral_type"].where(
            engineered["collateral_type"].notna(), "None"
        )

    # The one-hot encoder cannot handle NaN categoricals; replace any missing
    # categorical value with an explicit "Unknown" token (encoder ignores unseen
    # categories at inference, so this maps to an all-zero vector — safe for live
    # records that omit some fields).
    for col in config.CATEGORICAL_FEATURES:
        engineered[col] = engineered[col].astype("object").where(engineered[col].notna(), "Unknown")

    # Return columns in the canonical order the pipeline expects.
    return engineered[config.ALL_FEATURES]
