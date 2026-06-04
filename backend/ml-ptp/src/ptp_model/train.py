"""Train the PTP-fulfillment classifier.

Decisions baked in (per project owner):
  * Binary classification: label = 1 when ptp_kept >= PTP_KEPT_THRESHOLD.
  * Train only on accounts that were actually given a PTP (ptp_given == 1).
  * Calibrated probability output so the score is a usable P(fulfill).

Model: HistGradientBoostingClassifier (handles NaN natively, strong on tabular data),
wrapped in CalibratedClassifierCV (isotonic) for well-calibrated probabilities.
"""

from __future__ import annotations

import argparse
import json

import joblib
import numpy as np
import pandas as pd
from sklearn.calibration import CalibratedClassifierCV
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.inspection import permutation_importance
from sklearn.metrics import (
    average_precision_score,
    brier_score_loss,
    classification_report,
    confusion_matrix,
    precision_recall_curve,
    roc_auc_score,
)
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder

from . import config
from .features import engineer_features


def _load_dataset(path) -> pd.DataFrame:
    df = pd.read_csv(path)
    # Decision: model only PTP-given accounts.
    df = df[df["ptp_given"] == 1].reset_index(drop=True)
    return df


def _build_estimator() -> CalibratedClassifierCV:
    preprocessor = ColumnTransformer(
        transformers=[
            (
                "cat",
                OneHotEncoder(handle_unknown="ignore", min_frequency=0.01),
                config.CATEGORICAL_FEATURES,
            ),
            # Numeric columns pass through; HistGradientBoosting handles NaN natively.
            ("num", "passthrough", config.NUMERIC_FEATURES),
        ],
        remainder="drop",
    )
    clf = HistGradientBoostingClassifier(
        learning_rate=0.05,
        max_iter=400,
        max_depth=None,
        max_leaf_nodes=31,
        l2_regularization=1.0,
        early_stopping=True,
        validation_fraction=0.15,
        # Counter the class imbalance (~24% positives) so the rarer "will fulfill"
        # class gets enough weight during training — standard for imbalanced data.
        class_weight="balanced",
        random_state=config.RANDOM_SEED,
    )
    pipe = Pipeline([("prep", preprocessor), ("clf", clf)])
    # Isotonic calibration for trustworthy probabilities.
    return CalibratedClassifierCV(pipe, method="isotonic", cv=5)


def train(data_path=config.TRAINING_CSV) -> dict:
    df = _load_dataset(data_path)
    y = (df[config.RAW_TARGET_COL] >= config.PTP_KEPT_THRESHOLD).astype(int)
    X = engineer_features(df)

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=config.RANDOM_SEED, stratify=y
    )

    model = _build_estimator()
    model.fit(X_train, y_train)

    proba = model.predict_proba(X_test)[:, 1]

    # Tune the decision threshold to the F1-optimal operating point instead of a blind
    # 0.5 — standard practice for imbalanced data; lifts recall while keeping calibration.
    prec, rec, thr = precision_recall_curve(y_test, proba)
    f1_curve = 2 * prec * rec / (prec + rec + 1e-12)
    decision_threshold = float(thr[int(f1_curve[:-1].argmax())]) if len(thr) else 0.5
    pred = (proba >= decision_threshold).astype(int)

    metrics = {
        "roc_auc": float(roc_auc_score(y_test, proba)),
        "pr_auc": float(average_precision_score(y_test, proba)),
        "brier_score": float(brier_score_loss(y_test, proba)),
        "decision_threshold": decision_threshold,
        "positive_rate": float(y.mean()),
        "n_train": int(len(X_train)),
        "n_test": int(len(X_test)),
        "confusion_matrix": confusion_matrix(y_test, pred).tolist(),
    }

    print("=" * 64)
    print("PTP fulfillment model — evaluation (held-out 20%)")
    print("=" * 64)
    print(f"  ROC-AUC      : {metrics['roc_auc']:.3f}")
    print(f"  PR-AUC       : {metrics['pr_auc']:.3f}")
    print(f"  Brier score  : {metrics['brier_score']:.3f}  (lower = better calibrated)")
    print(f"  Positive rate: {metrics['positive_rate']:.3f}")
    print(f"  Decision thr : {metrics['decision_threshold']:.3f}  (F1-optimal, tuned)")
    print(f"  Train / Test : {metrics['n_train']} / {metrics['n_test']}")
    print(f"\nClassification report @ tuned threshold ({decision_threshold:.3f}):")
    print(classification_report(y_test, pred, digits=3))

    # Global feature importance (permutation) for explainability in the UI.
    perm = permutation_importance(
        model, X_test, y_test, n_repeats=8, random_state=config.RANDOM_SEED, scoring="roc_auc"
    )
    importances = sorted(
        ({"feature": f, "importance": float(imp)} for f, imp in zip(X.columns, perm.importances_mean)),
        key=lambda d: d["importance"],
        reverse=True,
    )
    print("\nTop 12 features (permutation importance on ROC-AUC):")
    for row in importances[:12]:
        label = config.FEATURE_LABELS.get(row["feature"], row["feature"])
        print(f"  {row['importance']:+.4f}  {label}")

    # Persist artifacts.
    config.MODELS_DIR.mkdir(parents=True, exist_ok=True)
    joblib.dump(model, config.MODEL_PATH)

    # Population reference stats used by the serving layer for per-account explanations.
    numeric_medians = {c: float(X[c].median()) for c in config.NUMERIC_FEATURES if X[c].notna().any()}
    metadata = {
        "model_version": config.__dict__.get("__version__", "0.1.0"),
        "threshold": config.PTP_KEPT_THRESHOLD,
        "decision_threshold": decision_threshold,
        "target": config.TARGET_COL,
        "trained_on": "PTP-given accounts (ptp_given == 1)",
        "data_path": str(data_path),
        "metrics": metrics,
        "global_importances": importances,
        "numeric_medians": numeric_medians,
        "features": {"numeric": config.NUMERIC_FEATURES, "categorical": config.CATEGORICAL_FEATURES},
        "note": (
            "Trained on synthetic data generated from the project's data spec. Metrics are "
            "illustrative; swap TRAINING_CSV for real labeled outcomes to productionize."
        ),
    }
    config.METADATA_PATH.write_text(json.dumps(metadata, indent=2))
    print(f"\nSaved model    -> {config.MODEL_PATH}")
    print(f"Saved metadata -> {config.METADATA_PATH}")
    return metadata


def main() -> None:
    parser = argparse.ArgumentParser(description="Train the PTP fulfillment model.")
    parser.add_argument("-d", "--data", type=str, default=str(config.TRAINING_CSV))
    args = parser.parse_args()
    train(args.data)


if __name__ == "__main__":
    main()
