"""FastAPI scoring service for PTP fulfillment probability.

Endpoints
---------
GET  /health              liveness + model metadata
POST /predict             score a single account
POST /predict/batch       score many accounts

The Spring Boot backend calls /predict in real time when an agent logs a PTP
disposition, and surfaces probability + band + top_factors on the disposition screen.
"""

from __future__ import annotations

import json

import joblib
import pandas as pd
from fastapi import FastAPI, HTTPException

from . import config, payment_model
from .features import engineer_features
from .schema import (
    AccountFeatures,
    BatchRequest,
    BatchResponse,
    Factor,
    PTPPrediction,
    SubScore,
)

# Direction each feature pushes the fulfillment probability (for explanation only).
# +1 => higher value raises P(fulfill); -1 => higher value lowers it.
_FACTOR_DIRECTION = {
    "pay_paid_ratio": +1,
    "response_rate": +1,
    "call_pickup_rate": +1,
    "cibil_score": +1,
    "internal_score": +1,
    "avg_days_to_pay": +1,
    "pay_missed_ratio": -1,
    "pay_returned_ratio": -1,
    "broken_ptp_count": -1,
    "latest_dpd": -1,
    "credit_utilization_pct": -1,
    "escalation_flag": -1,
    "npa_flag": -1,
    "outstanding_ratio": -1,
    "days_since_last_contact": -1,
}

app = FastAPI(title="PTP Fulfillment Model", version=config.__dict__.get("__version__", "0.1.0"))

_state: dict = {"model": None, "metadata": None}


def _load() -> None:
    if not config.MODEL_PATH.exists():
        raise RuntimeError(
            f"Model not found at {config.MODEL_PATH}. Run `uv run ptp-generate` then `uv run ptp-train` first."
        )
    _state["model"] = joblib.load(config.MODEL_PATH)
    _state["metadata"] = json.loads(config.METADATA_PATH.read_text())
    # Additive: load the payment-probability models (no-op if files absent).
    _state["payment_loaded"] = payment_model.load()


@app.on_event("startup")
def _startup() -> None:
    _load()


def _band(p: float) -> str:
    # Shared band thresholds: High >= 0.90, Medium >= 0.70, Low < 0.70.
    return config.likelihood_band(p)


def _top_factors(engineered_row: pd.Series, n: int = 4) -> list[Factor]:
    """Pick the globally most-important features present for this account and report
    their direction of influence. Heuristic 'key drivers' view (not exact SHAP)."""
    metadata = _state["metadata"]
    factors: list[Factor] = []
    for item in metadata["global_importances"]:
        feat = item["feature"]
        if feat not in engineered_row.index:
            continue
        val = engineered_row[feat]
        if pd.isna(val):
            continue
        direction = _FACTOR_DIRECTION.get(feat)
        if direction is None:
            continue
        # Compare to population median to decide if this account's value helps or hurts.
        median = metadata["numeric_medians"].get(feat)
        if median is None:
            impact = "positive" if direction > 0 else "negative"
        else:
            above = float(val) >= median
            helps = (above and direction > 0) or (not above and direction < 0)
            impact = "positive" if helps else "negative"
        factors.append(
            Factor(
                feature=feat,
                label=config.FEATURE_LABELS.get(feat, feat),
                value=round(float(val), 4) if isinstance(val, (int, float)) else str(val),
                impact=impact,
            )
        )
        if len(factors) >= n:
            break
    return factors


def _predict_frame(df_raw: pd.DataFrame) -> list[PTPPrediction]:
    model = _state["model"]
    metadata = _state["metadata"]
    X = engineer_features(df_raw)
    proba = model.predict_proba(X)[:, 1]
    # Use the F1-tuned decision threshold saved at train time (falls back to 0.5).
    threshold = metadata.get("decision_threshold", metadata.get("threshold", 0.5))

    # Payment-probability models (15d / 30d) — scored on the raw account frame.
    payment = payment_model.predict(df_raw)

    def _sub(arr, i) -> SubScore | None:
        if arr is None:
            return None
        prob = float(arr[i])
        return SubScore(probability=round(prob, 4), band=config.likelihood_band(prob))

    preds: list[PTPPrediction] = []
    for i in range(len(X)):
        p = float(proba[i])
        acc_id = df_raw.iloc[i].get("account_id")
        preds.append(
            PTPPrediction(
                account_id=str(acc_id) if acc_id is not None and pd.notna(acc_id) else None,
                probability=round(p, 4),
                fulfilled=p >= threshold,
                band=_band(p),
                threshold=threshold,
                top_factors=_top_factors(X.iloc[i]),
                payment_probability_15d=_sub(payment["prob_15"], i),
                payment_probability_30d=_sub(payment["prob_30"], i),
                model_version=str(metadata.get("model_version", "0.1.0")),
            )
        )
    return preds


@app.get("/health")
def health() -> dict:
    md = _state["metadata"] or {}
    return {
        "status": "ok" if _state["model"] is not None else "model_not_loaded",
        "model_version": md.get("model_version"),
        "threshold": md.get("threshold"),
        "metrics": md.get("metrics"),
    }


@app.post("/reload")
def reload() -> dict:
    """Hot-reload the model + metadata from disk (call after re-training, no restart needed)."""
    _load()
    md = _state["metadata"] or {}
    return {"status": "reloaded", "model_version": md.get("model_version"), "metrics": md.get("metrics")}


@app.post("/predict", response_model=PTPPrediction)
def predict(account: AccountFeatures) -> PTPPrediction:
    if _state["model"] is None:
        raise HTTPException(status_code=503, detail="Model not loaded")
    df = pd.DataFrame([account.model_dump()])
    return _predict_frame(df)[0]


@app.post("/predict/batch", response_model=BatchResponse)
def predict_batch(req: BatchRequest) -> BatchResponse:
    if _state["model"] is None:
        raise HTTPException(status_code=503, detail="Model not loaded")
    if not req.accounts:
        return BatchResponse(predictions=[])
    df = pd.DataFrame([a.model_dump() for a in req.accounts])
    return BatchResponse(predictions=_predict_frame(df))


def main() -> None:
    import uvicorn

    uvicorn.run("ptp_model.app:app", host="0.0.0.0", port=8000, reload=False)


if __name__ == "__main__":
    main()
