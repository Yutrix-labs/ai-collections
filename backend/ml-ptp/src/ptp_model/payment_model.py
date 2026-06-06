"""Payment-probability models (15-day / 30-day).

Serves the 15d/30d payment probabilities from the bundled ``collections_models_v1.pkl``
artifact (LightGBM, trained in the ptp_prob_lightgbm notebook). The artifact is a dict
holding five model heads; only the two payment regressors (``p15``, ``p30``) are used
here. They consume a 41-column raw account frame whose 13 categorical columns are
label-encoded with the encoders bundled in the artifact.

Integration is additive — if the artifact file is absent, prediction returns ``None`` and
the PTP path is unaffected.

NOTE on accuracy: the artifact was trained on synthetic data whose payment targets are a
deterministic function of the input features, so its headline R² is not a real-world
metric. Several of its expected inputs (e.g. self_cure_probability, ptp_kept,
paid_after_days) are not supplied by the backend and are imputed as missing at serve time.
"""

from __future__ import annotations

import pickle
import warnings

import numpy as np
import pandas as pd

from . import config

_state: dict = {
    "p15": None,
    "p30": None,
    "label_encoders": None,
    "features": None,
    "cat_cols": None,
}


def load() -> bool:
    """Load the p15/p30 payment regressors from the bundled artifact. False if missing."""
    if not config.PAYMENT_BUNDLE_PATH.exists():
        return False
    with warnings.catch_warnings():
        # Silence the sklearn pickle version-mismatch notice (models predict fine).
        warnings.simplefilter("ignore")
        with open(config.PAYMENT_BUNDLE_PATH, "rb") as f:
            artifact = pickle.load(f)

    models = artifact["models"]
    _state["p15"] = models["p15"]
    _state["p30"] = models["p30"]
    _state["label_encoders"] = artifact.get("label_encoders", {})
    # Use the model's own feature order so X always matches what it was trained on.
    _state["features"] = list(_state["p15"].booster_.feature_name())
    # Categorical columns that actually have a stored label encoder.
    _state["cat_cols"] = [
        c for c in artifact.get("categorical_features", []) if c in _state["label_encoders"]
    ]
    return True


def is_loaded() -> bool:
    return _state["p15"] is not None


def _encode_categorical(values: pd.Series, le) -> pd.Series:
    """Apply a stored LabelEncoder to a raw column.

    Unseen or missing values map to the encoder's ``"Missing"`` class if it has one,
    else to code 0 — both are within the trained category set, so LightGBM's stored
    categorical mapping stays aligned.
    """
    class_to_code = {c: i for i, c in enumerate(le.classes_)}
    fallback = class_to_code.get("Missing", 0)
    s = values.where(values.notna(), "Missing").astype(str)
    return s.map(lambda v: class_to_code.get(v, fallback)).astype("int64")


def _prepare(df_raw: pd.DataFrame) -> pd.DataFrame:
    """Build the 41-feature matrix the LightGBM models expect from a raw account frame.

    Missing columns are created (NaN numeric / ``"Missing"`` categorical). Categoricals are
    label-encoded with the stored encoders and set to ``category`` dtype, mirroring training
    so the booster's stored categorical codes line up. Numerics are coerced (LightGBM
    handles NaN natively).
    """
    features = _state["features"]
    encoders = _state["label_encoders"]
    cat_cols = set(_state["cat_cols"])

    X = pd.DataFrame(index=df_raw.index)
    for col in features:
        if col in df_raw.columns:
            src = df_raw[col]
        else:
            src = pd.Series([np.nan] * len(df_raw), index=df_raw.index)
        if col in cat_cols:
            X[col] = _encode_categorical(src, encoders[col]).astype("category")
        else:
            X[col] = pd.to_numeric(src, errors="coerce")

    return X[features]


def predict(df_raw: pd.DataFrame) -> dict:
    """Return {"prob_15": np.ndarray|None, "prob_30": np.ndarray|None} for the rows in df_raw."""
    if not is_loaded():
        return {"prob_15": None, "prob_30": None}

    X = _prepare(df_raw)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        prob_15 = np.clip(_state["p15"].predict(X), 0.0, 1.0)
        prob_30_raw = np.clip(_state["p30"].predict(X), 0.0, 1.0)

    # Enforce the monotonic rule used at train time: 30-day probability >= 15-day.
    prob_30 = np.maximum(prob_15, prob_30_raw)
    return {"prob_15": prob_15, "prob_30": prob_30}
