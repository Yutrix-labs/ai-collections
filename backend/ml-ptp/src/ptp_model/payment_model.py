"""Payment-probability models (15-day / 30-day).

Two externally-trained LightGBM classifiers (from the POC_3Jun2026 work) predict the
probability that an account pays within 15 / 30 days. They consume the same raw account
schema as the PTP model, with 13 categorical columns mapped via the bundled cat_mappings.

This module loads them once and scores a raw account DataFrame, returning both
probabilities. Integration is additive — if the model files are absent, prediction
returns ``None`` and the PTP path is unaffected.
"""

from __future__ import annotations

import warnings

import joblib
import numpy as np
import pandas as pd

from . import config

_state: dict = {"model_15": None, "model_30": None, "cat_mappings": None, "features": None}


def load() -> bool:
    """Load both models + categorical mappings. Returns False if files are missing."""
    if not all(
        p.exists()
        for p in (
            config.PAYMENT_MODEL_15_PATH,
            config.PAYMENT_MODEL_30_PATH,
            config.PAYMENT_CAT_MAPPINGS_PATH,
        )
    ):
        return False
    _state["model_15"] = joblib.load(config.PAYMENT_MODEL_15_PATH)
    _state["model_30"] = joblib.load(config.PAYMENT_MODEL_30_PATH)
    _state["cat_mappings"] = joblib.load(config.PAYMENT_CAT_MAPPINGS_PATH)
    # Use the model's own feature order so X always matches what it was trained on.
    _state["features"] = list(_state["model_30"].feature_name_)
    return True


def is_loaded() -> bool:
    return _state["model_30"] is not None


def _prepare(df_raw: pd.DataFrame) -> pd.DataFrame:
    """Build the exact feature matrix the LightGBM models expect from a raw account frame.

    Missing columns are created as NaN (LightGBM handles missing natively); categorical
    columns are coerced to the model's known category set (unknown/missing -> NaN).
    """
    features = _state["features"]
    cat_mappings = _state["cat_mappings"]

    X = pd.DataFrame(index=df_raw.index)
    for col in features:
        X[col] = df_raw[col] if col in df_raw.columns else np.nan

    for col, categories in cat_mappings.items():
        if col in X.columns:
            X[col] = X[col].astype("object").astype("category").cat.set_categories(categories)

    for col in features:
        if col not in cat_mappings:
            X[col] = pd.to_numeric(X[col], errors="coerce")

    return X[features]


def predict(df_raw: pd.DataFrame) -> dict:
    """Return {"prob_15": np.ndarray|None, "prob_30": np.ndarray|None} for the rows in df_raw."""
    if not is_loaded():
        return {"prob_15": None, "prob_30": None}

    X = _prepare(df_raw)
    with warnings.catch_warnings():
        # Silence the sklearn pickle version-mismatch notice (models predict fine).
        warnings.simplefilter("ignore")
        prob_15 = _state["model_15"].predict_proba(X)[:, 1]
        prob_30 = _state["model_30"].predict_proba(X)[:, 1]

    return {"prob_15": prob_15, "prob_30": prob_30}
