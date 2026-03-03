# Action History & Payment History Fields — Design

## Goal

Add two new schema-module fields — `action_history` and `payment_history` — to the Phase 1 synthetic collections data generator, and convert all PII fields to English script.

## Approach: New `"interactions"` Schema Module

Both new fields are added under a new optional schema module `"interactions"`, consistent with the existing `"demographic"` and `"bureau"` module pattern. Activating the module adds both fields to every generated record.

---

## Field Definitions

### `action_history`

A list of collection actions taken by agents **after** the initial collection call. Each entry represents one contact attempt or follow-up action.

```json
[
  {"seq": 1, "action": "CALL",    "channel": "phone",  "outcome": "PTP",         "days_since_call": 0},
  {"seq": 2, "action": "SMS",     "channel": "sms",    "outcome": "NO_RESPONSE", "days_since_call": 3},
  {"seq": 3, "action": "CALL",    "channel": "phone",  "outcome": "PAYMENT",     "days_since_call": 7}
]
```

**Fields per entry:**

| Field | Type | Description |
|---|---|---|
| `seq` | int | Sequence number (1-based) |
| `action` | str | Action type: `CALL`, `SMS`, `EMAIL`, `VISIT`, `LEGAL_NOTICE` |
| `channel` | str | Contact channel: `phone`, `sms`, `email`, `field`, `legal` |
| `outcome` | str | Result: `PTP`, `PAYMENT`, `NO_RESPONSE`, `CALLBACK`, `DISPUTE`, `SETTLED` |
| `days_since_call` | int | Days elapsed since the original collection call |

**Generation rules:**

- Number of entries: 1–5, correlated with `dpd_bucket` (higher DPD → more actions)
- `outcome` weights are correlated with `risk_tier` (prime → higher PTP/PAYMENT rate)
- `action` distribution varies by `dpd_bucket`:
  - current/early: mostly CALL/SMS
  - mild/severe: CALL/SMS/EMAIL mix
  - npa: includes VISIT and LEGAL_NOTICE
- `days_since_call` increases monotonically within a sequence (3–30 day spread)
- Final outcome in sequence is consistent with `resolution_status` and `target_paid_30d`

---

### `payment_history`

A list of actual payment events that occurred after the collection call. Empty list if `target_paid_30d = 0`.

```json
[
  {"seq": 1, "days_after_call": 7,  "amount_paid": 5000.0,  "payment_type": "PARTIAL", "channel": "upi"},
  {"seq": 2, "days_after_call": 22, "amount_paid": 10000.0, "payment_type": "FULL",    "channel": "bank_transfer"}
]
```

**Fields per entry:**

| Field | Type | Description |
|---|---|---|
| `seq` | int | Sequence number (1-based) |
| `days_after_call` | int | Days after collection call that payment was received |
| `amount_paid` | float | Payment amount in INR (rounded to nearest 100) |
| `payment_type` | str | `FULL`, `PARTIAL`, `MINIMUM` |
| `channel` | str | `upi`, `bank_transfer`, `cash`, `cheque`, `auto_debit` |

**Generation rules:**

- Empty list when `target_paid_30d = 0` or `resolution_status = "Written-off"`
- 1–3 entries when `target_paid_30d = 1`
- `FULL` payment preferred for prime/near_prime; `PARTIAL` more common for sub_prime/npa
- `amount_paid` sampled as a fraction of `emi_amount` for PARTIAL/MINIMUM, or `emi_amount` for FULL
- `channel` weights: UPI 45%, bank_transfer 25%, cash 15%, cheque 10%, auto_debit 5%
- `days_after_call` increases monotonically, within 0–30 day window

---

## Consistency Constraints (HARD rules)

| Condition | Enforced behaviour |
|---|---|
| `target_paid_30d = 0` | `payment_history = []` |
| `resolution_status = "Written-off"` | `payment_history = []`, no PAYMENT outcome in `action_history` |
| `resolution_status = "PTP"` | At least one `action_history` entry with `outcome = "PTP"` |
| `resolution_status = "Settled"` | Last `action_history` outcome must be `SETTLED` or `PAYMENT` |
| `resolution_status = "Legal"` | At least one `action_history` entry with `action = "LEGAL_NOTICE"` |

---

## English Locale Conversion

`_faker = Faker("hi_IN")` → `_faker = Faker("en_IN")`

`en_IN` (English-India locale) provides:
- English-script names (e.g., "Priya Sharma", "Rajesh Kumar")
- Indian city names in English (e.g., "Mumbai", "Hyderabad")
- Indian state names in English (e.g., "Maharashtra", "Telangana")

No other changes required — the locale swap is a one-line change in `phase1_faker_generator.py`.

---

## API Changes

`generate_record()` and `generate_dataset()` — no signature changes. Module activated via existing `schema_modules` parameter:

```python
df = generate_dataset(n=10_000, schema_modules=["demographic", "bureau", "interactions"])
```

`config_default.json` `schema_modules` array updated to include `"interactions"` as an available value.

---

## CSV/Excel Export

`action_history` and `payment_history` are serialised as JSON strings in CSV export (standard approach for nested columns in tabular ML datasets). The feature manifest will document them as `list[dict]` type.

---

## ML Use Case

These fields enable training a **next-best-action** recommendation model:

- **Input features**: customer profile (segment, risk_tier, dpd_bucket, outstanding_amount) + `action_history` sequence
- **Target**: next action that leads to a payment outcome
- Suitable for sequence models (LSTM, Transformer) or flattened tabular models (encode last N actions as features)
