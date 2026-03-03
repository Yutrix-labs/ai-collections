# Action History & Payment History Fields — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add `action_history` and `payment_history` (post-call) fields as an `"interactions"` schema module, and convert Faker locale from `hi_IN` (Devanagari) to `en_IN` (English-script Indian names/places).

**Architecture:** New fields follow the existing schema-module pattern — activated via `schema_modules=["interactions"]` in `generate_record()`. Domain constants for actions/outcomes/channels are added to `domain_definitions.py`. The ml_exporter is updated to serialize list-valued columns as JSON strings in CSV output.

**Tech Stack:** Python 3.11, Faker (`en_IN` locale), pytest, pandas

---

## Reference Files

- `domain_definitions.py` — add interaction constants (Tasks 1, 2)
- `phase1_faker_generator.py` — locale fix + two new generator functions + module wiring (Tasks 1, 3, 4, 5)
- `ml_exporter.py` — JSON-serialize list columns on CSV export (Task 6)
- `config_default.json` — add `"interactions"` to schema_modules enum (Task 7)
- `tests/test_domain_definitions.py` — tests for new constants (Task 2)
- `tests/test_faker_generator.py` — tests for locale + new generators (Tasks 1, 3, 4, 5)
- `tests/test_ml_exporter.py` — test JSON serialisation of list columns (Task 6)

---

### Task 1: English Locale Fix

**Files:**
- Modify: `phase1_faker_generator.py:21`
- Modify: `tests/test_faker_generator.py` (add 1 test)

**Context:** `_faker = Faker("hi_IN")` generates Devanagari script. Replace with `en_IN` for English-script Indian names/places. Only the locale string changes — all call sites stay the same.

**Step 1: Write the failing test**

Add this test to `tests/test_faker_generator.py`:

```python
def test_demographic_fields_are_ascii():
    """Names, cities, states must be ASCII (English script, not Devanagari)."""
    rng = random.Random(1)
    record = generate_record(rng=rng, schema_modules=["demographic"])
    for field in ("name", "city", "state"):
        value = record[field]
        assert value.isascii(), (
            f"Field '{field}' contains non-ASCII characters: {value!r}. "
            "Locale must be en_IN not hi_IN."
        )
```

**Step 2: Run to verify it fails**

```
cd "C:\Users\joshm\OneDrive\Documents\Ebix collections\collections-synth-data"
pytest tests/test_faker_generator.py::test_demographic_fields_are_ascii -v
```

Expected: FAIL — `name` will contain Devanagari characters.

**Step 3: Apply the fix**

In `phase1_faker_generator.py` line 21, change:

```python
_faker = Faker("hi_IN")
```

to:

```python
_faker = Faker("en_IN")
```

**Step 4: Run to verify it passes**

```
pytest tests/test_faker_generator.py::test_demographic_fields_are_ascii -v
```

Expected: PASS

**Step 5: Run full suite**

```
pytest -v -m "not slow"
```

Expected: all tests pass (50+ tests).

**Step 6: Commit**

```bash
git add phase1_faker_generator.py tests/test_faker_generator.py
git commit -m "fix: convert Faker locale from hi_IN (Devanagari) to en_IN (English-script)"
```

---

### Task 2: Interaction Domain Constants

**Files:**
- Modify: `domain_definitions.py` (append to end of file)
- Modify: `tests/test_domain_definitions.py` (add 4 tests)

**Context:** Add all constants needed by the interaction generators — action type lists, outcome lists, channel mappings, and probability weight tables. All weights are plain integers (same pattern as existing constants).

**Step 1: Write the failing tests**

Add to `tests/test_domain_definitions.py`:

```python
from domain_definitions import (
    ACTION_TYPES, ACTION_OUTCOMES, PAYMENT_CHANNELS, PAYMENT_TYPES,
    ACTION_TYPE_WEIGHTS, ACTION_OUTCOME_WEIGHTS, ACTION_COUNT_RANGES,
    PAYMENT_TYPE_WEIGHTS,
)

def test_action_types_are_strings():
    assert all(isinstance(a, str) for a in ACTION_TYPES)
    assert "CALL" in ACTION_TYPES
    assert "LEGAL_NOTICE" in ACTION_TYPES

def test_action_outcome_weights_sum_per_tier():
    """Each risk tier must have outcome weights for every ACTION_OUTCOME."""
    for tier in ["prime", "near_prime", "sub_prime", "npa"]:
        weights = ACTION_OUTCOME_WEIGHTS[tier]
        assert set(weights.keys()) == set(ACTION_OUTCOMES), (
            f"Tier '{tier}' missing outcomes: {set(ACTION_OUTCOMES) - set(weights.keys())}"
        )
        assert sum(weights.values()) > 0

def test_action_count_ranges_cover_all_buckets():
    from domain_definitions import DPD_BUCKETS
    for bucket in DPD_BUCKETS:
        lo, hi = ACTION_COUNT_RANGES[bucket]
        assert 1 <= lo <= hi <= 5, f"Bad count range for bucket {bucket}: ({lo}, {hi})"

def test_payment_type_weights_cover_all_tiers():
    from domain_definitions import RISK_TIERS
    for tier in RISK_TIERS:
        weights = PAYMENT_TYPE_WEIGHTS[tier]
        assert set(weights.keys()) == set(PAYMENT_TYPES), (
            f"Tier '{tier}' missing payment types"
        )
        assert sum(weights.values()) > 0
```

**Step 2: Run to verify they fail**

```
pytest tests/test_domain_definitions.py::test_action_types_are_strings tests/test_domain_definitions.py::test_action_outcome_weights_sum_per_tier tests/test_domain_definitions.py::test_action_count_ranges_cover_all_buckets tests/test_domain_definitions.py::test_payment_type_weights_cover_all_tiers -v
```

Expected: 4 FAIL — names not imported.

**Step 3: Add constants to `domain_definitions.py`**

Append after the last constant (`DEFAULT_RISK_WEIGHTS`) at the bottom of the file:

```python
# ---------------------------------------------------------------------------
# --- Interactions module constants (action_history & payment_history) ---
# ---------------------------------------------------------------------------

# Action types (what the agent did)
ACTION_TYPES = ["CALL", "SMS", "EMAIL", "VISIT", "LEGAL_NOTICE"]

# Outcomes of each action
ACTION_OUTCOMES = ["PTP", "PAYMENT", "NO_RESPONSE", "CALLBACK", "DISPUTE", "SETTLED"]

# Channel mapped from action type (used to set channel field)
ACTION_CHANNEL_MAP = {
    "CALL":         "phone",
    "SMS":          "sms",
    "EMAIL":        "email",
    "VISIT":        "field",
    "LEGAL_NOTICE": "legal",
}

# Payment channels for post-call payment events
PAYMENT_CHANNELS = ["upi", "bank_transfer", "cash", "cheque", "auto_debit"]

# Weights for payment channels (same for all tiers)
PAYMENT_CHANNEL_WEIGHTS = [45, 25, 15, 10, 5]

# Payment types
PAYMENT_TYPES = ["FULL", "PARTIAL", "MINIMUM"]

# Number of action entries per record, by dpd_bucket
ACTION_COUNT_RANGES = {
    "current": (1, 2),
    "early":   (1, 3),
    "mild":    (2, 4),
    "severe":  (3, 5),
    "npa":     (3, 5),
}

# Action type weights by dpd_bucket
# Higher DPD → more escalated actions (VISIT, LEGAL_NOTICE)
ACTION_TYPE_WEIGHTS = {
    "current": {"CALL": 60, "SMS": 30, "EMAIL": 10, "VISIT": 0,  "LEGAL_NOTICE": 0},
    "early":   {"CALL": 55, "SMS": 30, "EMAIL": 15, "VISIT": 0,  "LEGAL_NOTICE": 0},
    "mild":    {"CALL": 50, "SMS": 25, "EMAIL": 20, "VISIT": 5,  "LEGAL_NOTICE": 0},
    "severe":  {"CALL": 40, "SMS": 20, "EMAIL": 15, "VISIT": 15, "LEGAL_NOTICE": 10},
    "npa":     {"CALL": 30, "SMS": 15, "EMAIL": 10, "VISIT": 20, "LEGAL_NOTICE": 25},
}

# Action outcome weights by risk_tier
# Prime customers more likely to PTP/pay; NPA more likely to not respond
ACTION_OUTCOME_WEIGHTS = {
    "prime":      {"PTP": 35, "PAYMENT": 25, "NO_RESPONSE": 20, "CALLBACK": 15, "DISPUTE": 4,  "SETTLED": 1},
    "near_prime": {"PTP": 30, "PAYMENT": 20, "NO_RESPONSE": 25, "CALLBACK": 15, "DISPUTE": 8,  "SETTLED": 2},
    "sub_prime":  {"PTP": 20, "PAYMENT": 15, "NO_RESPONSE": 35, "CALLBACK": 15, "DISPUTE": 13, "SETTLED": 2},
    "npa":        {"PTP": 10, "PAYMENT":  8, "NO_RESPONSE": 50, "CALLBACK": 12, "DISPUTE": 15, "SETTLED": 5},
}

# Post-call payment type weights by risk_tier
# Prime more likely to pay FULL; NPA more likely to pay PARTIAL or MINIMUM
PAYMENT_TYPE_WEIGHTS = {
    "prime":      {"FULL": 60, "PARTIAL": 30, "MINIMUM": 10},
    "near_prime": {"FULL": 45, "PARTIAL": 40, "MINIMUM": 15},
    "sub_prime":  {"FULL": 20, "PARTIAL": 50, "MINIMUM": 30},
    "npa":        {"FULL": 10, "PARTIAL": 45, "MINIMUM": 45},
}
```

**Step 4: Run to verify tests pass**

```
pytest tests/test_domain_definitions.py -v
```

Expected: all 17 tests pass.

**Step 5: Commit**

```bash
git add domain_definitions.py tests/test_domain_definitions.py
git commit -m "feat: add interaction domain constants (action/payment history)"
```

---

### Task 3: `_generate_action_history()` Function

**Files:**
- Modify: `phase1_faker_generator.py` (add function before `generate_record`)
- Modify: `tests/test_faker_generator.py` (add 5 tests)

**Context:** This generates the sequence of collection actions taken post-call. It must:
- Enforce consistency with `resolution_status` (PTP → at least one PTP outcome; Legal → at least one LEGAL_NOTICE action; Settled → last outcome is SETTLED or PAYMENT; Written-off → no PAYMENT outcome).
- Keep `days_since_call` monotonically increasing.
- Zero-weight actions are excluded from sampling by filtering.

**Step 1: Write the failing tests**

Add to `tests/test_faker_generator.py`:

```python
from phase1_faker_generator import _generate_action_history  # add to imports at top

def test_action_history_structure():
    """Each entry must have all required fields with valid values."""
    import random as _random
    from domain_definitions import ACTION_TYPES, ACTION_OUTCOMES
    rng = _random.Random(42)
    history = _generate_action_history("mild", "near_prime", "Open", 0, rng)
    assert isinstance(history, list)
    assert 1 <= len(history) <= 5
    for i, entry in enumerate(history):
        assert set(entry.keys()) == {"seq", "action", "channel", "outcome", "days_since_call"}
        assert entry["seq"] == i + 1
        assert entry["action"] in ACTION_TYPES
        assert entry["outcome"] in ACTION_OUTCOMES

def test_action_history_days_monotonic():
    """days_since_call must be non-decreasing across entries."""
    import random as _random
    rng = _random.Random(7)
    history = _generate_action_history("severe", "sub_prime", "PTP", 1, rng)
    days = [e["days_since_call"] for e in history]
    assert days == sorted(days), f"days_since_call not monotonic: {days}"

def test_action_history_ptp_resolution_has_ptp_outcome():
    """resolution_status=PTP must produce at least one PTP outcome."""
    import random as _random
    found_ptp = False
    for seed in range(20):
        rng = _random.Random(seed)
        history = _generate_action_history("mild", "near_prime", "PTP", 1, rng)
        if any(e["outcome"] == "PTP" for e in history):
            found_ptp = True
            break
    assert found_ptp, "No PTP outcome found in any of 20 seeds for PTP resolution"

def test_action_history_written_off_no_payment():
    """Written-off records must have no PAYMENT outcome in action_history."""
    import random as _random
    for seed in range(20):
        rng = _random.Random(seed)
        history = _generate_action_history("npa", "npa", "Written-off", 0, rng)
        assert not any(e["outcome"] == "PAYMENT" for e in history), (
            f"PAYMENT outcome found in Written-off record (seed={seed})"
        )

def test_action_history_legal_has_legal_notice():
    """resolution_status=Legal must produce at least one LEGAL_NOTICE action."""
    import random as _random
    found = False
    for seed in range(20):
        rng = _random.Random(seed)
        history = _generate_action_history("npa", "npa", "Legal", 0, rng)
        if any(e["action"] == "LEGAL_NOTICE" for e in history):
            found = True
            break
    assert found, "No LEGAL_NOTICE action found in 20 seeds for Legal resolution"
```

**Step 2: Run to verify they fail**

```
pytest tests/test_faker_generator.py::test_action_history_structure tests/test_faker_generator.py::test_action_history_days_monotonic tests/test_faker_generator.py::test_action_history_ptp_resolution_has_ptp_outcome tests/test_faker_generator.py::test_action_history_written_off_no_payment tests/test_faker_generator.py::test_action_history_legal_has_legal_notice -v
```

Expected: 5 FAIL — `_generate_action_history` not defined.

**Step 3: Add function to `phase1_faker_generator.py`**

Add the following imports at the top of `phase1_faker_generator.py` (extend the existing import from `domain_definitions`):

```python
from domain_definitions import (
    RISK_TIERS, SEGMENTS, LOAN_TYPES, DPD_BUCKETS,
    MARKOV_MATRICES, MARKOV_INIT, CIBIL_RANGES,
    RESOLUTION_DIST, CONTACT_ATTEMPTS_RANGES, OUTSTANDING_RANGES,
    BASE_PAID_PROB, DEFAULT_DPD_WEIGHTS, DEFAULT_SEGMENT_WEIGHTS,
    DEFAULT_RISK_WEIGHTS,
    # interactions
    ACTION_TYPES, ACTION_OUTCOMES, ACTION_CHANNEL_MAP, PAYMENT_CHANNELS,
    PAYMENT_CHANNEL_WEIGHTS, PAYMENT_TYPES, ACTION_COUNT_RANGES,
    ACTION_TYPE_WEIGHTS, ACTION_OUTCOME_WEIGHTS, PAYMENT_TYPE_WEIGHTS,
)
```

Add the function before `generate_record()`:

```python
def _generate_action_history(
    dpd_bucket: str,
    risk_tier: str,
    resolution_status: str,
    target_paid_30d: int,
    rng: random.Random,
) -> list[dict]:
    """Generate a list of collection actions taken post-call."""
    lo, hi = ACTION_COUNT_RANGES[dpd_bucket]
    n_actions = rng.randint(lo, hi)

    # Build action type pool — exclude zero-weight actions
    type_weights = ACTION_TYPE_WEIGHTS[dpd_bucket]
    valid_actions = [a for a in ACTION_TYPES if type_weights[a] > 0]
    valid_action_weights = [type_weights[a] for a in valid_actions]

    # Build outcome pool — Written-off must never produce PAYMENT
    outcome_weights_raw = ACTION_OUTCOME_WEIGHTS[risk_tier]
    if resolution_status == "Written-off":
        outcome_pool = {k: v for k, v in outcome_weights_raw.items() if k != "PAYMENT"}
    else:
        outcome_pool = outcome_weights_raw

    outcome_keys = list(outcome_pool.keys())
    outcome_vals = list(outcome_pool.values())

    # Generate raw actions
    actions = []
    day = 0
    for seq in range(1, n_actions + 1):
        action = rng.choices(valid_actions, weights=valid_action_weights, k=1)[0]
        outcome = rng.choices(outcome_keys, weights=outcome_vals, k=1)[0]
        day += rng.randint(1, max(1, 28 // n_actions))
        day = min(day, 28)
        actions.append({
            "seq":             seq,
            "action":          action,
            "channel":         ACTION_CHANNEL_MAP[action],
            "outcome":         outcome,
            "days_since_call": day,
        })

    # Consistency overrides on the last entry
    last = actions[-1]

    if resolution_status == "PTP" and not any(e["outcome"] == "PTP" for e in actions):
        last["outcome"] = "PTP"

    if resolution_status == "Settled":
        last["outcome"] = "SETTLED"

    if resolution_status == "Legal" and not any(e["action"] == "LEGAL_NOTICE" for e in actions):
        last["action"] = "LEGAL_NOTICE"
        last["channel"] = ACTION_CHANNEL_MAP["LEGAL_NOTICE"]

    return actions
```

**Step 4: Run to verify tests pass**

```
pytest tests/test_faker_generator.py::test_action_history_structure tests/test_faker_generator.py::test_action_history_days_monotonic tests/test_faker_generator.py::test_action_history_ptp_resolution_has_ptp_outcome tests/test_faker_generator.py::test_action_history_written_off_no_payment tests/test_faker_generator.py::test_action_history_legal_has_legal_notice -v
```

Expected: 5 PASS

**Step 5: Run full suite**

```
pytest -v -m "not slow"
```

Expected: all tests pass.

**Step 6: Commit**

```bash
git add phase1_faker_generator.py tests/test_faker_generator.py
git commit -m "feat: add _generate_action_history() for post-call action sequence"
```

---

### Task 4: `_generate_payment_history_post_call()` Function

**Files:**
- Modify: `phase1_faker_generator.py` (add function)
- Modify: `tests/test_faker_generator.py` (add 4 tests)

**Context:** Generates post-call payment events. Empty list when `target_paid_30d = 0` or `resolution_status = "Written-off"`. Note: this is completely separate from the existing `_generate_payment_history()` which generates the 12-character Markov sequence for `payment_history_12m`.

**Step 1: Write the failing tests**

Add to `tests/test_faker_generator.py`:

```python
from phase1_faker_generator import _generate_payment_history_post_call  # add to imports

def test_payment_history_post_call_empty_when_not_paid():
    """payment_history must be empty when target_paid_30d = 0."""
    import random as _random
    for seed in range(10):
        rng = _random.Random(seed)
        result = _generate_payment_history_post_call(0, "Open", 5000.0, "sub_prime", rng)
        assert result == [], f"Expected [] for target_paid_30d=0 (seed={seed}), got {result}"

def test_payment_history_post_call_empty_for_written_off():
    """Written-off records must have empty payment_history."""
    import random as _random
    for seed in range(10):
        rng = _random.Random(seed)
        result = _generate_payment_history_post_call(0, "Written-off", 5000.0, "npa", rng)
        assert result == []

def test_payment_history_post_call_structure_when_paid():
    """When paid, each entry must have correct fields."""
    import random as _random
    from domain_definitions import PAYMENT_TYPES, PAYMENT_CHANNELS
    rng = _random.Random(42)
    result = _generate_payment_history_post_call(1, "PTP", 10000.0, "prime", rng)
    assert len(result) >= 1
    for i, entry in enumerate(result):
        assert set(entry.keys()) == {"seq", "days_after_call", "amount_paid", "payment_type", "channel"}
        assert entry["seq"] == i + 1
        assert entry["payment_type"] in PAYMENT_TYPES
        assert entry["channel"] in PAYMENT_CHANNELS
        assert entry["amount_paid"] > 0

def test_payment_history_post_call_days_monotonic():
    """days_after_call must be non-decreasing."""
    import random as _random
    for seed in range(10):
        rng = _random.Random(seed)
        result = _generate_payment_history_post_call(1, "Open", 8000.0, "near_prime", rng)
        if result:
            days = [e["days_after_call"] for e in result]
            assert days == sorted(days), f"days_after_call not monotonic: {days}"
```

**Step 2: Run to verify they fail**

```
pytest tests/test_faker_generator.py::test_payment_history_post_call_empty_when_not_paid tests/test_faker_generator.py::test_payment_history_post_call_empty_for_written_off tests/test_faker_generator.py::test_payment_history_post_call_structure_when_paid tests/test_faker_generator.py::test_payment_history_post_call_days_monotonic -v
```

Expected: 4 FAIL

**Step 3: Add function to `phase1_faker_generator.py`**

Add immediately after `_generate_action_history()`:

```python
def _generate_payment_history_post_call(
    target_paid_30d: int,
    resolution_status: str,
    emi_amount: float,
    risk_tier: str,
    rng: random.Random,
) -> list[dict]:
    """Generate post-call payment events. Empty when not paid or written-off."""
    if target_paid_30d == 0 or resolution_status == "Written-off":
        return []

    n_payments = rng.randint(1, 3)
    type_weights = PAYMENT_TYPE_WEIGHTS[risk_tier]
    ptype_keys = list(type_weights.keys())
    ptype_vals = list(type_weights.values())

    payments = []
    day = 0
    for seq in range(1, n_payments + 1):
        payment_type = rng.choices(ptype_keys, weights=ptype_vals, k=1)[0]

        if payment_type == "FULL":
            amount = emi_amount
        elif payment_type == "PARTIAL":
            amount = round(emi_amount * rng.uniform(0.30, 0.79), -2)
        else:  # MINIMUM
            amount = round(emi_amount * rng.uniform(0.10, 0.29), -2)
        amount = max(amount, 100.0)

        day += rng.randint(1, max(1, 28 // n_payments))
        day = min(day, 30)

        channel = rng.choices(PAYMENT_CHANNELS, weights=PAYMENT_CHANNEL_WEIGHTS, k=1)[0]

        payments.append({
            "seq":            seq,
            "days_after_call": day,
            "amount_paid":    amount,
            "payment_type":   payment_type,
            "channel":        channel,
        })

    return payments
```

**Step 4: Run to verify tests pass**

```
pytest tests/test_faker_generator.py::test_payment_history_post_call_empty_when_not_paid tests/test_faker_generator.py::test_payment_history_post_call_empty_for_written_off tests/test_faker_generator.py::test_payment_history_post_call_structure_when_paid tests/test_faker_generator.py::test_payment_history_post_call_days_monotonic -v
```

Expected: 4 PASS

**Step 5: Run full suite**

```
pytest -v -m "not slow"
```

Expected: all tests pass.

**Step 6: Commit**

```bash
git add phase1_faker_generator.py tests/test_faker_generator.py
git commit -m "feat: add _generate_payment_history_post_call() for post-call payment events"
```

---

### Task 5: Wire `"interactions"` Module into `generate_record()`

**Files:**
- Modify: `phase1_faker_generator.py` (update `generate_record`)
- Modify: `tests/test_faker_generator.py` (add 3 tests)

**Context:** Add a check for `"interactions"` in the `schema_modules` section of `generate_record()`, calling both new generators and adding `action_history` and `payment_history` to the record dict. Fields `resolution_status` and `target_paid_30d` are already computed before the schema_modules block, so they can be passed directly.

**Step 1: Write the failing tests**

Add to `tests/test_faker_generator.py`:

```python
def test_interactions_module_adds_fields():
    """schema_modules=['interactions'] must add action_history and payment_history."""
    import random as _random
    rng = _random.Random(42)
    record = generate_record(rng=rng, schema_modules=["interactions"])
    assert "action_history" in record, "action_history missing from record"
    assert "payment_history" in record, "payment_history missing from record"
    assert isinstance(record["action_history"], list)
    assert isinstance(record["payment_history"], list)

def test_interactions_absent_without_module():
    """Without 'interactions' module, action_history and payment_history must not appear."""
    import random as _random
    rng = _random.Random(42)
    record = generate_record(rng=rng, schema_modules=[])
    assert "action_history" not in record
    assert "payment_history" not in record

def test_interactions_payment_history_empty_when_written_off():
    """For Written-off records, payment_history must be empty list."""
    import random as _random
    for seed in range(100):
        rng = _random.Random(seed)
        record = generate_record(
            rng=rng,
            dpd_bucket="npa",
            schema_modules=["interactions"],
        )
        if record["resolution_status"] == "Written-off":
            assert record["payment_history"] == [], (
                f"Written-off record has non-empty payment_history (seed={seed})"
            )
            break
    # If no Written-off record found in 100 seeds, skip — bucket distribution makes it rare
```

**Step 2: Run to verify they fail**

```
pytest tests/test_faker_generator.py::test_interactions_module_adds_fields tests/test_faker_generator.py::test_interactions_absent_without_module tests/test_faker_generator.py::test_interactions_payment_history_empty_when_written_off -v
```

Expected: first two FAIL, third may PASS by coincidence.

**Step 3: Update `generate_record()` in `phase1_faker_generator.py`**

Find the `schema_modules` block near the end of `generate_record()` (currently lines 222-226) and extend it:

```python
    # Optional schema modules
    schema_modules = schema_modules or []
    if "demographic" in schema_modules:
        record.update(_generate_demographic_fields(rng))
    if "bureau" in schema_modules:
        record.update(_generate_bureau_fields(dpd_bucket, rng))
    if "interactions" in schema_modules:
        record["action_history"] = _generate_action_history(
            dpd_bucket, risk_tier, resolution_status, target_paid_30d, rng
        )
        record["payment_history"] = _generate_payment_history_post_call(
            target_paid_30d, resolution_status, emi_amount, risk_tier, rng
        )

    return record
```

**Step 4: Run to verify tests pass**

```
pytest tests/test_faker_generator.py::test_interactions_module_adds_fields tests/test_faker_generator.py::test_interactions_absent_without_module tests/test_faker_generator.py::test_interactions_payment_history_empty_when_written_off -v
```

Expected: all 3 PASS

**Step 5: Run full suite**

```
pytest -v -m "not slow"
```

Expected: all tests pass.

**Step 6: Commit**

```bash
git add phase1_faker_generator.py tests/test_faker_generator.py
git commit -m "feat: wire 'interactions' schema module into generate_record()"
```

---

### Task 6: JSON Serialisation of List Columns in CSV Export

**Files:**
- Modify: `ml_exporter.py` — update `export_csv()` to serialize list/dict columns as JSON strings
- Modify: `tests/test_ml_exporter.py` (add 1 test)

**Context:** `action_history` and `payment_history` are Python lists. When pandas writes these to CSV without pre-processing, it uses Python's `repr()` format (e.g., `[{'seq': 1, ...}]`) which is not valid JSON and can't be read back. We must serialize them to proper JSON strings using `json.dumps` before writing.

The serialisation must only apply to columns containing lists — check with a helper that inspects the first non-null value in each column.

**Step 1: Write the failing test**

Add to `tests/test_ml_exporter.py`:

```python
import json as _json

def test_list_columns_serialised_as_json_in_csv(tmp_path):
    """action_history and payment_history must be valid JSON strings in CSV, not Python repr."""
    import sys, os
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
    from phase1_faker_generator import generate_dataset
    from ml_exporter import split_dataset, export_csv
    import pandas as pd

    df = generate_dataset(n=50, seed=1, schema_modules=["interactions"])
    train, val, test = split_dataset(df)
    export_csv(train, val, test, str(tmp_path))

    # Read back full CSV and check action_history column
    full_csv = pd.read_csv(tmp_path / "synthetic_collections.csv")
    assert "action_history" in full_csv.columns
    # Every non-null value must parse as valid JSON
    for val_str in full_csv["action_history"].dropna():
        parsed = _json.loads(val_str)  # raises json.JSONDecodeError if not valid JSON
        assert isinstance(parsed, list)
```

**Step 2: Run to verify it fails**

```
pytest tests/test_ml_exporter.py::test_list_columns_serialised_as_json_in_csv -v
```

Expected: FAIL — `json.JSONDecodeError` because pandas writes Python repr, not JSON.

**Step 3: Update `export_csv()` in `ml_exporter.py`**

Replace the current `export_csv` function body with:

```python
def export_csv(
    train: pd.DataFrame,
    val: pd.DataFrame,
    test: pd.DataFrame,
    output_dir: str = "outputs",
) -> None:
    """Write train/val/test and full dataset CSVs to output_dir.

    List-valued columns (e.g., action_history, payment_history) are serialised
    to JSON strings so the CSV is machine-readable.
    """
    os.makedirs(output_dir, exist_ok=True)

    full = pd.concat([train, val, test], ignore_index=True)

    def _serialise_lists(df: pd.DataFrame) -> pd.DataFrame:
        """Return a copy with list-valued columns serialised to JSON strings."""
        df = df.copy()
        for col in df.columns:
            first_val = df[col].dropna().iloc[0] if df[col].notna().any() else None
            if isinstance(first_val, list):
                df[col] = df[col].apply(
                    lambda v: json.dumps(v) if isinstance(v, list) else v
                )
        return df

    _serialise_lists(full).to_csv(os.path.join(output_dir, "synthetic_collections.csv"), index=False)
    _serialise_lists(train).to_csv(os.path.join(output_dir, "train.csv"), index=False)
    _serialise_lists(val).to_csv(os.path.join(output_dir, "val.csv"), index=False)
    _serialise_lists(test).to_csv(os.path.join(output_dir, "test.csv"), index=False)
```

**Step 4: Run to verify test passes**

```
pytest tests/test_ml_exporter.py::test_list_columns_serialised_as_json_in_csv -v
```

Expected: PASS

**Step 5: Run full suite**

```
pytest -v -m "not slow"
```

Expected: all tests pass.

**Step 6: Commit**

```bash
git add ml_exporter.py tests/test_ml_exporter.py
git commit -m "feat: serialise list-valued columns as JSON strings in CSV export"
```

---

### Task 7: Update Config and Final Verification

**Files:**
- Modify: `config_default.json` — add `"interactions"` to schema_modules
- Run: full test suite + end-to-end smoke test

**Context:** The config schema already has `schema_modules` as an array. Just add `"interactions"` to the default config's list. Then run the full suite including slow tests to verify nothing is broken.

**Step 1: Read current config**

Open `config_default.json` and check the current `schema_modules` value. It will be an empty array `[]` or contain `["demographic", "bureau"]`.

**Step 2: Update `config_default.json`**

The file currently looks like:

```json
{
  "schema_version": "1.0",
  "record_count": 10000,
  "output_format": ["csv", "excel"],
  "ml_task": "binary_classification",
  "class_balance_target": 0.80,
  "dpd_weights": null,
  "segment_weights": null,
  "schema_modules": []
}
```

Change `schema_modules` to:

```json
  "schema_modules": ["demographic", "bureau", "interactions"]
```

**Step 3: Verify CLI still works**

```
cd "C:\Users\joshm\OneDrive\Documents\Ebix collections\collections-synth-data"
py generate.py --records 100 --seed 42 --output outputs/test_run/
```

Expected: prints record count and output paths, no errors. Verify `outputs/test_run/synthetic_collections.csv` has columns `action_history` and `payment_history` containing JSON strings.

**Step 4: Run full test suite including slow tests**

```
pytest -v
```

Expected: 60+ tests pass (29 existing faker tests + 9 new = 38 faker tests, 17 domain tests, 9 exporter tests, 3 e2e).

**Step 5: Commit**

```bash
git add config_default.json
git commit -m "feat: enable interactions module in default config"
```

---

## Summary

| Task | What it does | Tests added |
|---|---|---|
| 1 | Faker locale → `en_IN` | 1 |
| 2 | Interaction domain constants | 4 |
| 3 | `_generate_action_history()` | 5 |
| 4 | `_generate_payment_history_post_call()` | 4 |
| 5 | Wire `"interactions"` into `generate_record()` | 3 |
| 6 | JSON serialise list columns in CSV export | 1 |
| 7 | Update config + final verification | 0 |

**Total new tests: 18** (bringing suite to ~68 tests)
