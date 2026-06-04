"""Smoke tests: generation signal, feature engineering, and the scoring path."""

from __future__ import annotations

import numpy as np
import pandas as pd

from ptp_model import config
from ptp_model.features import engineer_features
from ptp_model.generate_data import generate


def test_generation_has_signal():
    """Regenerated data must show a real positive correlation between historical
    paid-ratio and ptp_kept (the relationship the spec wires in)."""
    df = generate(n_rows=2000, seed=1)
    given = df[df["ptp_given"] == 1].copy()
    paid_ratio = given["payment_history"].str.count("P") / given["payment_history"].str.len()
    corr = np.corrcoef(paid_ratio, given["ptp_kept"])[0, 1]
    assert corr > 0.3, f"expected paid_ratio↔ptp_kept signal, got {corr:.3f}"


def test_engineer_features_shape_and_columns():
    df = generate(n_rows=50, seed=2)
    X = engineer_features(df)
    assert list(X.columns) == config.ALL_FEATURES
    assert len(X) == 50
    # Engineered ratios are bounded.
    assert X["pay_paid_ratio"].between(0, 1).all()


def test_engineer_features_handles_missing_columns():
    """Single live record with only a few fields must still produce all features."""
    partial = pd.DataFrame([{"account_id": "X", "response_rate": 0.6, "payment_history": "PPPPPR"}])
    X = engineer_features(partial)
    assert list(X.columns) == config.ALL_FEATURES
    assert X["pay_paid_ratio"].iloc[0] > 0.7


def test_scoring_path():
    """Model + metadata load and produce a valid probability for a sample account."""
    import json

    import joblib

    if not config.MODEL_PATH.exists():
        import pytest

        pytest.skip("model not trained yet")

    model = joblib.load(config.MODEL_PATH)
    json.loads(config.METADATA_PATH.read_text())
    df = generate(n_rows=5, seed=3)
    X = engineer_features(df)
    proba = model.predict_proba(X)[:, 1]
    assert ((proba >= 0) & (proba <= 1)).all()
