# PTP Fulfillment Model (`ml-ptp`)

A production-shaped ML microservice that predicts the **probability a customer will
fulfill a Promise-to-Pay (PTP)**. It complements the existing Java backend and Python
listening-agent in the AI Collections monorepo.

```
Spring Boot backend ──HTTP──▶ ml-ptp (FastAPI) ──▶ calibrated P(fulfill PTP) + drivers
        │                                                       │
        └────────────── disposition screen (Next.js) ◀──────────┘
```

## Design decisions (locked with the project owner)

| Decision | Choice |
|---|---|
| Task | **Binary classification** → calibrated `P(fulfill PTP)` |
| Label | `ptp_fulfilled = 1` when `ptp_kept >= 0.5` |
| Training population | **PTP-given accounts only** (`ptp_given == 1`) |
| Serving | **Python FastAPI microservice**, called by Spring Boot |
| Data | Synthetic, generated from the project data spec (see below) |

## Why we regenerate the data

The shipped `Data_distribution.xlsx` has **near-zero correlation** between features and
`ptp_kept` — its generator never wired in the Section-7 relationships. `generate_data.py`
reproduces them faithfully so the targets carry real, learnable signal:

- `ptp_given ~ Bernoulli(0.35 + 0.30 · response_rate)` — responsive customers promise more
- `ptp_kept ~ Beta(2,3)` blended 30% toward the customer's **historical paid-ratio**
  (from `payment_history`), with mild delinquency / weak-credit penalties; `0` if no PTP
- `broken_ptp_count ~ NegBinom` whose mean grows with unkept promises

Features are **bootstrapped** from the real sample so realistic joint distributions and
inter-feature correlations are preserved; only the three PTP columns are regenerated.

## Quickstart

```bash
cd backend/ml-ptp
uv sync                 # installs into .venv (Python 3.12)

uv run ptp-generate     # -> data/ptp_training_data.csv  (~5000 rows, real signal)
uv run ptp-train        # -> models/ptp_model.joblib + model_metadata.json
uv run ptp-serve        # FastAPI on http://0.0.0.0:8000
uv run pytest           # smoke tests
```

`ptp-generate -n 10000` to make a bigger set; `ptp-train -d <csv>` to train on real data later.

## Current model performance (held-out 20%, synthetic data)

| Metric | Value |
|---|---|
| ROC-AUC | **0.79** |
| PR-AUC | 0.55 |
| Brier score | 0.15 (well-calibrated) |
| Recall (will-fulfill) | **0.74** |
| Decision threshold | 0.24 (F1-tuned) |
| Positive rate | 0.24 |

Two standard, low-effort accuracy levers are applied: **`class_weight="balanced"`** (counters
the 24% positive imbalance) and an **F1-optimal decision threshold** tuned at train time and
saved in metadata (serving uses it for the `fulfilled` flag). This lifts will-fulfill recall
from ~0.25 to ~0.74 while keeping calibration intact.

Top drivers (permutation importance): historical paid-ratio ≫ CIBIL score > days-past-due
> broken-PTP count. **These numbers are illustrative** — they reflect the synthetic
generator. Point `ptp-train` at real labeled outcomes to productionize; no code changes
needed.

## API

`GET /health` — liveness + model metadata/metrics.

`POST /reload` — hot-reload the model + metadata from disk after re-training (no restart).
So the retrain → live flow is just: `uv run ptp-train && curl -X POST localhost:8000/reload`.

`POST /predict` — score one account. Body = any subset of the raw account fields
(see `schema.AccountFeatures`); missing fields are imputed/handled.

```jsonc
// response
{
  "account_id": "ACC0000001",
  "probability": 0.6357,        // calibrated P(fulfill PTP)
  "fulfilled": true,            // probability >= threshold (0.5)
  "band": "Medium",             // High >=0.90, Medium >=0.70, Low <0.70 (shared by all scores)
  "threshold": 0.24,
  "top_factors": [              // key drivers for the disposition screen
    {"feature": "pay_paid_ratio", "label": "Historical on-time payment ratio",
     "value": 0.8333, "impact": "positive"},
    ...
  ],
  "payment_probability_15d": {"probability": 0.47, "band": "Low"},     // P(pays within 15 days)
  "payment_probability_30d": {"probability": 0.78, "band": "Medium"},  // P(pays within 30 days)
  "model_version": "0.1.0"
}
```

### Payment-probability models (integrated)

`/predict` also returns 15-day and 30-day payment probabilities from two externally-trained
**LightGBM** models (`models/payment/model_15d.pkl`, `model_30d.pkl`, `cat_mappings.pkl`). They
consume the same raw account schema and are scored alongside the PTP model. Integration is
additive — if the `.pkl` files are absent, those fields return `null` and the PTP path is
unaffected. Likelihood bands are shared across all three scores: **High ≥0.90, Medium ≥0.70,
Low <0.70**.

`POST /predict/batch` — `{ "accounts": [ {…}, {…} ] }` → `{ "predictions": [ … ] }`.

## Model

- `HistGradientBoostingClassifier` (handles NaN natively, strong on tabular data)
- One-hot encoding for categoricals; missing categoricals → `"Unknown"`
- `CalibratedClassifierCV` (isotonic) so `probability` is a trustworthy P(fulfill)
- Leakage explicitly excluded from features: `ptp_kept` (target source),
  `self_cure_probability` (derived score), `paid_after_days` (post-outcome)

## Integration with Spring Boot

Add a config-driven client (base URL e.g. `ptp.model.base-url=http://localhost:8000`) and
call `POST /predict` when an agent logs a PTP disposition. Map the response into the
`ApiResponse<T>` wrapper and the disposition/copilot card. Surface `probability` (as a %),
`band`, and `top_factors` on the detailed disposition screen so agents see *why* the model
expects the promise to hold or break.

## Files

```
src/ptp_model/
  config.py        # paths, target def, feature lists, generation params
  generate_data.py # config-faithful synthetic data  (ptp-generate)
  features.py      # shared feature engineering (train + serve)
  train.py         # pipeline, calibration, metrics, artifacts  (ptp-train)
  schema.py        # pydantic request/response models
  app.py           # FastAPI service  (ptp-serve)
tests/test_smoke.py
data/   models/     # generated (gitignore-able)
```
