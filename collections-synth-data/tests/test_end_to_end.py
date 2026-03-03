"""
End-to-end validation: generate → split → baseline AUC check.
Run with: py -m pytest tests/test_end_to_end.py -v -m slow
"""
import pytest
import pandas as pd
import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import LabelEncoder
from sklearn.metrics import roc_auc_score

from phase1_faker_generator import generate_dataset
from ml_exporter import split_dataset


pytestmark = pytest.mark.slow


def _encode_categoricals(df: pd.DataFrame) -> pd.DataFrame:
    """Label-encode string columns for sklearn."""
    df = df.copy()
    for col in df.select_dtypes(include="object").columns:
        df[col] = LabelEncoder().fit_transform(df[col].astype(str))
    df = df.drop(columns=["customer_id", "account_id"], errors="ignore")
    return df


def test_baseline_auc_exceeds_065():
    """Phase 1 success criterion: LogReg AUC > 0.65 on generated data."""
    df = generate_dataset(
        n=10_000,
        seed=42,
        schema_modules=["demographic", "bureau"],
    )
    train, val, test = split_dataset(df)

    target = "target_paid_30d"
    train_enc = _encode_categoricals(train)
    test_enc  = _encode_categoricals(test)

    X_train = train_enc.drop(columns=[target])
    y_train = train_enc[target]
    X_test  = test_enc.drop(columns=[target])
    y_test  = test_enc[target]

    model = LogisticRegression(max_iter=500, random_state=42)
    model.fit(X_train, y_train)
    y_prob = model.predict_proba(X_test)[:, 1]
    auc = roc_auc_score(y_test, y_prob)

    print(f"\nBaseline AUC: {auc:.4f}")
    assert auc > 0.65, f"AUC {auc:.4f} below Phase 1 target of 0.65"


def test_segment_distribution_within_tolerance():
    """Generated segment distribution must be within ±5% of configured weights."""
    df = generate_dataset(n=10_000, seed=42)
    expected = {"Retail": 0.60, "SME": 0.20, "MSME": 0.15, "Corporate": 0.05}
    actual = df["segment"].value_counts(normalize=True).to_dict()
    for seg, exp_rate in expected.items():
        got = actual.get(seg, 0)
        assert abs(got - exp_rate) < 0.05, (
            f"Segment {seg}: expected {exp_rate:.0%}, got {got:.0%}"
        )


def test_dpd_distribution_within_tolerance():
    """DPD bucket distribution must be within ±5% of default weights."""
    df = generate_dataset(n=10_000, seed=42)
    expected = {
        "Current":        0.45,
        "Early (1-30)":   0.20,
        "Mild (31-60)":   0.15,
        "Severe (61-90)": 0.12,
        "NPA (90+)":      0.08,
    }
    actual = df["dpd_bucket"].value_counts(normalize=True).to_dict()
    for bucket, exp_rate in expected.items():
        got = actual.get(bucket, 0)
        assert abs(got - exp_rate) < 0.05, (
            f"Bucket {bucket}: expected {exp_rate:.0%}, got {got:.0%}"
        )
