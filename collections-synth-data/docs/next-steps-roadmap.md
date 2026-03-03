# Collections AI — Next Steps Roadmap

**Version:** 1.0
**Date:** 2026-03-03
**Audience:** Product, Engineering, Data Science

---

## Where We Are Today

The Phase 1 synthetic data generator is complete and live. It produces ML-ready Indian collections records with full field coverage across seven schema modules:

| Module | Fields generated |
|--------|-----------------|
| Core | DPD, risk tier, outstanding, payment history, resolution status |
| Demographic | Name, age, city, income band, employer type |
| Bureau | CIBIL score, internal score, bureau enquiries |
| Interactions | Action history, post-call payment events |
| Behavioural | Response rate, self-cure probability, call pickup rate, escalation flag |
| Communication | Preferred channel, WhatsApp opt-in, DND status, email deliverability |
| Collateral | Collateral type, LTV ratio, forced sale value, condition |
| **Next Action** | **Recommended action, channel, reason, priority, confidence** |

The `suggested_next_action` engine runs entirely on rules and domain knowledge — no real data required. It is transparent, auditable, and deterministic.

---

## The Gap

The engine's rules and weights are currently based on **domain judgment**, not empirical evidence. When a bank, NBFC, or utility company shares their historical collections data, we can:

1. Validate whether the engine's recommendations match what experienced agents actually did
2. Calibrate thresholds and weights using real outcomes
3. Amplify the real data synthetically to train ML models at scale
4. Close the loop by measuring whether AI recommendations improve recovery rates

---

## Recommended Next Steps

### Phase 2A — Data Ingestion & Mapping
*Prerequisite for everything else. Do this first.*

**Goal:** Accept a real institution's data export and normalise it to the engine's standard schema.

**What to build:**

#### ETL Mapper
A configurable mapping layer that translates institution-specific field names and value formats to the engine's standard schema.

```
Institution CSV / DB extract
        ↓
Field name mapping      (e.g. "days_past_due" → "dpd")
Value normalisation     (e.g. risk grade "A/B/C/D" → "prime/near_prime/sub_prime/npa")
Date parsing            (payment history string reconstruction from transaction log)
Validation & QA report  (missing fields, out-of-range values, referential integrity)
        ↓
Standard schema records → ready for engine
```

**Suggested implementation:**
- Config-driven mapping file (JSON) — one config per institution, no code changes
- Validation report highlighting fields that cannot be mapped (engine degrades gracefully for missing fields)
- Handles CSV, Excel, and common DB extracts (MySQL, PostgreSQL, Oracle)

**Deliverable:** `etl/mapper.py` + one sample config per institution type (bank, NBFC, utility)

**Effort:** 2–3 weeks

---

### Phase 2B — Outcome Validator
*Run in parallel with 2A once mapped data is available.*

**Goal:** Compare what the engine recommends against what agents actually did, and measure the difference in resolution outcomes.

**What it produces:**

```
For each historical account:
  - What the engine would have recommended
  - What the agent actually did
  - What the resolution outcome was (paid / settled / written-off / still open)

Aggregate report:
  - Agreement rate: how often does engine match agent decision?
  - Outcome rate by action: which actions led to resolution most often?
  - Cases where engine disagrees with agent — were agent outcomes better or worse?
```

**Why this matters:**
- If the engine agrees with experienced agents 80%+ of the time → rules are well-calibrated
- Where the engine disagrees → those cases are the most valuable for improvement
- Outcome rates by action tell you which actions actually work for which customer profiles

**Deliverable:** `validation/outcome_validator.py` + summary report template

**Effort:** 1–2 weeks

---

### Phase 2C — Weight Calibration
*Requires outcome data from 2B.*

**Goal:** Replace hand-crafted `ACTION_SIGNAL_WEIGHTS` in `domain_definitions.py` with statistically derived weights learned from real outcome data.

**Approach:**

For each account in the historical dataset, the six signal scores are already computable (they're deterministic functions of the account fields). The outcome (did this account resolve after this action?) is known.

This becomes a standard supervised learning problem:

```
Input:   6 signal scores per account × 9 candidate actions
Target:  did the account resolve? (binary)
Model:   logistic regression or gradient boosting (interpretable)
Output:  learned weight vector → replaces ACTION_SIGNAL_WEIGHTS
```

Logistic regression is preferred here because the learned weights are directly interpretable — you can show the institution exactly what the model learned.

**Hard rules are never touched** — they remain inviolable business logic.

**Deliverable:** `calibration/calibrate_weights.py` + updated `domain_definitions.py`

**Effort:** 2–3 weeks (including validation on held-out accounts)

---

### Phase 2D — SDV/CTGAN Amplification
*Requires mapped real data from 2A. Can run in parallel with 2B and 2C.*

**Goal:** Use the real institution data (even a small sample of 500–1000 accounts) as a seed to generate 50K–100K privacy-safe synthetic records that preserve the statistical relationships of the real data.

**Why:**
- Real collections datasets are small, heavily imbalanced, and contain PII
- ML models need scale to generalise
- Synthetic data generated from real statistics is safe to share, store, and use without regulatory risk

**Approach:**

```
Real seed data (anonymised)
        ↓
SDV (Synthetic Data Vault) or CTGAN learns:
  - Marginal distributions of each field
  - Correlations between fields (e.g. NPA accounts have lower CIBIL)
  - Conditional distributions (e.g. payment history given risk tier)
        ↓
Generate 50K–100K synthetic records
        ↓
Validate: synthetic distribution matches real distribution (KS test, coverage report)
        ↓
Use for model training at scale
```

**Privacy note:** The synthetic records contain no real customer data. Individual accounts cannot be reverse-engineered from the synthetic output.

**Deliverable:** `amplification/sdv_pipeline.py` + distribution validation report

**Effort:** 3–4 weeks

---

### Phase 3 — ML Model (Phase 2 Replacement)
*Requires calibrated data from 2C and amplified data from 2D.*

**Goal:** Replace the weighted scoring in Phase 2 of the engine with a trained ML model, while keeping all Phase 1 hard rules unchanged.

**Architecture:**

```
Current engine:
  Phase 1 (hard rules) → [if no match] → Phase 2 (weighted scoring)

Upgraded engine:
  Phase 1 (hard rules) → [if no match] → Phase 2 (ML model)
```

The output dict structure stays identical. The `action_scores` dict now contains model probabilities instead of weighted sums. No downstream changes required.

**Candidate models:**

| Model | Pros | Cons |
|-------|------|------|
| Gradient Boosted Trees (XGBoost/LightGBM) | High accuracy, handles mixed types | Less interpretable |
| Logistic Regression (multi-class) | Fully interpretable, fast | Lower accuracy |
| Neural network (small MLP) | Can learn complex patterns | Black box, needs more data |

Recommendation: start with gradient boosted trees for accuracy, keep logistic regression as the interpretable fallback for regulatory/audit purposes.

**Deliverable:** `models/next_action_model.py` + model card + evaluation report

**Effort:** 4–6 weeks

---

### Phase 4 — Feedback Loop
*Runs continuously once the engine is in production.*

**Goal:** Capture what agents actually did after receiving an AI recommendation, and what the outcome was — feeding this back into the calibration pipeline.

**What to capture per interaction:**

```python
{
    "account_id":          "ACC1234567",
    "engine_recommendation": "CALL_BACK",
    "engine_confidence":   0.82,
    "agent_action":        "CALL_BACK",       # did agent follow the recommendation?
    "agent_override":      False,
    "override_reason":     None,
    "outcome_30d":         "PAYMENT",         # what happened 30 days later?
    "outcome_90d":         "CLOSED",
}
```

This data feeds back into:
- Weight calibration (2C) — continuously improving
- Hard rule validation — are the rules still correctly calibrated?
- Agent behaviour analysis — where do agents override the AI and why?

**Deliverable:** Feedback schema + logging integration guide

**Effort:** 2–3 weeks (schema + logging); ongoing thereafter

---

## Summary Timeline

```
Month 1         Month 2         Month 3         Month 4+
────────────────────────────────────────────────────────
[2A ETL Mapper          ]
                [2B Outcome Validator  ]
                [2C Weight Calibration ]
                [2D SDV Amplification        ]
                                [3 ML Model          ]
                                                [4 Feedback Loop → ongoing]
```

---

## What the Institution Needs to Provide

| Data | Format | Minimum size | Notes |
|------|--------|-------------|-------|
| Account master | CSV / Excel / DB | 500+ accounts | DPD, outstanding, risk grade, loan type |
| Contact log | CSV / Excel / DB | All interactions for those accounts | Date, action type, outcome |
| Payment history | CSV / Excel / DB | 12 months preferred | Can reconstruct from transaction log |
| Resolution outcome | CSV / Excel / DB | For closed accounts | Settled / written-off / recovered amount |

**PII handling:** Names, addresses, phone numbers, and account numbers are not required. The engine works entirely on behavioural and financial features. If PII is included in the export, it is stripped during the ETL mapping step and never stored.

---

## What We Deliver Back

At each phase, the institution receives:

| Phase | Deliverable |
|-------|------------|
| 2A | Mapped dataset + QA report (field coverage, anomalies) |
| 2B | Outcome validation report (engine vs agent agreement, action effectiveness) |
| 2C | Calibrated engine + calibration report (which weights changed and by how much) |
| 2D | 50K–100K synthetic records + distribution validation report |
| 3 | Trained model + model card + evaluation on held-out accounts |
| 4 | Feedback schema + integration guide for their collections system |

---

## Open Questions for the Institution

Before starting, the following should be agreed:

1. **What is the primary optimisation target?** Recovery rate within 30 days? 90 days? Cost per recovery?
2. **Which actions are available to agents?** Some institutions restrict field visits or legal notices to certain account types.
3. **Are there regulatory constraints on contact frequency?** (RBI guidelines, TRAI DND regulations)
4. **What is the minimum confidence threshold for a recommendation to be shown to an agent?**
5. **Will agents be able to override the recommendation?** If yes, override reasons should be captured for the feedback loop.
6. **What collections system are they using?** (Nucleus, LLMS, Finacle, in-house) — determines ETL complexity.
