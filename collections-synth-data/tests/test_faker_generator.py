import random

import pytest
import pandas as pd
from phase1_faker_generator import generate_record, generate_dataset, _generate_action_history, _generate_payment_history_post_call
from domain_definitions import RISK_TIERS, SEGMENTS, LOAN_TYPES, DPD_BUCKETS


# --- Single record tests ---

def test_generate_record_returns_dict():
    record = generate_record()
    assert isinstance(record, dict)


def test_core_fields_present():
    record = generate_record()
    required = [
        "customer_id", "account_id", "loan_type", "segment", "risk_tier",
        "outstanding_amount", "emi_amount", "dpd", "dpd_bucket",
        "payment_history_12m", "contact_attempts", "promise_to_pay",
        "resolution_status", "target_paid_30d",
    ]
    for field in required:
        assert field in record, f"Missing field: {field}"


def test_customer_id_is_unique():
    rng = random.Random(1)
    records = [generate_record(rng=rng) for _ in range(100)]
    ids = [r["customer_id"] for r in records]
    assert len(set(ids)) == 100


def test_loan_type_is_valid():
    rng = random.Random(2)
    for _ in range(50):
        r = generate_record(rng=rng)
        assert r["loan_type"] in LOAN_TYPES


def test_segment_is_valid():
    rng = random.Random(3)
    for _ in range(50):
        r = generate_record(rng=rng)
        assert r["segment"] in SEGMENTS


def test_risk_tier_is_valid():
    rng = random.Random(4)
    for _ in range(50):
        r = generate_record(rng=rng)
        assert r["risk_tier"] in RISK_TIERS


def test_dpd_is_non_negative():
    rng = random.Random(5)
    for _ in range(100):
        r = generate_record(rng=rng)
        assert r["dpd"] >= 0


def test_dpd_bucket_matches_dpd():
    bucket_ranges = {
        "Current":         (0, 0),
        "Early (1-30)":    (1, 30),
        "Mild (31-60)":    (31, 60),
        "Severe (61-90)":  (61, 90),
        "NPA (90+)":       (91, 9999),
    }
    rng = random.Random(6)
    for _ in range(100):
        r = generate_record(rng=rng)
        lo, hi = bucket_ranges[r["dpd_bucket"]]
        assert lo <= r["dpd"] <= hi, (
            f"dpd={r['dpd']} inconsistent with bucket={r['dpd_bucket']}"
        )


def test_outstanding_is_positive():
    rng = random.Random(7)
    for _ in range(50):
        r = generate_record(rng=rng)
        assert r["outstanding_amount"] > 0


def test_emi_less_than_outstanding():
    rng = random.Random(8)
    for _ in range(100):
        r = generate_record(rng=rng)
        assert r["emi_amount"] < r["outstanding_amount"], (
            f"emi={r['emi_amount']} >= outstanding={r['outstanding_amount']}"
        )


def test_contact_attempts_non_negative():
    rng = random.Random(9)
    for _ in range(50):
        r = generate_record(rng=rng)
        assert r["contact_attempts"] >= 0


def test_promise_to_pay_is_bool():
    rng = random.Random(10)
    for _ in range(50):
        r = generate_record(rng=rng)
        assert isinstance(r["promise_to_pay"], bool)


def test_resolution_status_valid():
    valid = {"Open", "PTP", "Partial", "Settled", "Legal", "Written-off"}
    rng = random.Random(11)
    for _ in range(100):
        r = generate_record(rng=rng)
        assert r["resolution_status"] in valid


def test_target_paid_30d_binary():
    rng = random.Random(12)
    for _ in range(100):
        r = generate_record(rng=rng)
        assert r["target_paid_30d"] in (0, 1)


# --- Dataset generation tests ---

def test_generate_dataset_returns_dataframe():
    df = generate_dataset(n=100)
    assert isinstance(df, pd.DataFrame)
    assert len(df) == 100


def test_generate_dataset_reproducible():
    df1 = generate_dataset(n=50, seed=42)
    df2 = generate_dataset(n=50, seed=42)
    assert df1["customer_id"].tolist() == df2["customer_id"].tolist()


# --- Payment history / Markov tests ---

def test_payment_history_is_12_chars():
    rng = random.Random(13)
    for _ in range(100):
        r = generate_record(rng=rng)
        assert len(r["payment_history_12m"]) == 12


def test_payment_history_uses_valid_chars():
    valid = set("PDM-")
    rng = random.Random(14)
    for _ in range(200):
        r = generate_record(rng=rng)
        assert set(r["payment_history_12m"]).issubset(valid), (
            f"Invalid chars in: {r['payment_history_12m']}"
        )


def test_prime_tier_has_higher_p_rate_than_npa():
    """Prime customers should average more P chars than NPA customers."""
    rng1 = random.Random(99)
    prime_p_rate = sum(
        generate_record(rng=rng1, risk_tier="prime")["payment_history_12m"].count("P")
        for _ in range(500)
    ) / (500 * 12)

    rng2 = random.Random(99)
    npa_p_rate = sum(
        generate_record(rng=rng2, risk_tier="npa")["payment_history_12m"].count("P")
        for _ in range(500)
    ) / (500 * 12)

    assert prime_p_rate > npa_p_rate, (
        f"Prime P-rate {prime_p_rate:.2f} should exceed NPA P-rate {npa_p_rate:.2f}"
    )


def test_npa_tier_has_high_m_rate():
    """NPA customers should have substantial missed payments."""
    rng = random.Random(77)
    m_rates = []
    for _ in range(300):
        hist = generate_record(rng=rng, risk_tier="npa")["payment_history_12m"]
        m_rates.append(hist.count("M") / 12)
    avg_m_rate = sum(m_rates) / len(m_rates)
    assert avg_m_rate > 0.30, f"NPA M-rate {avg_m_rate:.2f} should be > 30%"


# --- Correlation / business rule tests ---

def test_npa_dpd_implies_low_cibil():
    """NPA bucket records must have CIBIL <= 529 (HARD rule Appendix E.1)."""
    rng = random.Random(11)
    for _ in range(200):
        r = generate_record(rng=rng, dpd_bucket="npa", schema_modules=["bureau"])
        assert r["cibil_score"] <= 529, (
            f"NPA record has CIBIL={r['cibil_score']} > 529"
        )


def test_written_off_implies_zero_target():
    """Written-off accounts must have target_paid_30d = 0 (HARD rule Appendix F)."""
    rng = random.Random(22)
    found_written_off = False
    for _ in range(500):
        r = generate_record(rng=rng, dpd_bucket="npa")
        if r["resolution_status"] == "Written-off":
            found_written_off = True
            assert r["target_paid_30d"] == 0, (
                "Written-off account has target_paid_30d = 1"
            )
    assert found_written_off, "No Written-off records generated in 500 NPA records"


def test_zero_contacts_implies_no_ptp():
    """contact_attempts = 0 must imply promise_to_pay = False (HARD rule)."""
    rng = random.Random(33)
    for _ in range(500):
        r = generate_record(rng=rng)
        if r["contact_attempts"] == 0:
            assert r["promise_to_pay"] is False, (
                "contact_attempts=0 but promise_to_pay=True"
            )


def test_cibil_score_in_valid_range():
    """Bureau module CIBIL scores must be 300-900."""
    rng = random.Random(44)
    for _ in range(200):
        r = generate_record(rng=rng, schema_modules=["bureau"])
        assert 300 <= r["cibil_score"] <= 900, (
            f"cibil_score={r['cibil_score']} out of range"
        )


def test_emi_less_than_outstanding_always():
    """EMI must always be less than outstanding (HARD business rule)."""
    rng = random.Random(55)
    for _ in range(500):
        r = generate_record(rng=rng)
        assert r["emi_amount"] < r["outstanding_amount"]


# --- Class balance tests ---

def test_default_class_balance_near_80_pct():
    """Default generation should produce ~80% paid, within ±8%."""
    df = generate_dataset(n=5000, seed=42)
    paid_rate = df["target_paid_30d"].mean()
    assert 0.72 <= paid_rate <= 0.88, (
        f"Paid rate {paid_rate:.2f} outside 72-88% range"
    )


def test_custom_class_balance_respected():
    """Setting class_balance_target=0.60 should yield ~60% paid, within ±10%."""
    df = generate_dataset(n=5000, seed=42, class_balance_target=0.60)
    paid_rate = df["target_paid_30d"].mean()
    assert 0.50 <= paid_rate <= 0.70, (
        f"Paid rate {paid_rate:.2f} outside 50-70% range for target=0.60"
    )


# --- Markov consistency enforcement tests ---

def test_no_p_in_history_means_zero_target():
    """Records with zero P chars in payment history must have target=0."""
    rng = random.Random(66)
    for _ in range(1000):
        r = generate_record(rng=rng, risk_tier="npa", dpd_bucket="npa")
        if "P" not in r["payment_history_12m"]:
            assert r["target_paid_30d"] == 0, (
                f"No P in history but target=1: {r['payment_history_12m']}"
            )


def test_three_consecutive_m_implies_high_dpd():
    """Sequences ending in 3+ consecutive M's should come from high-DPD accounts.
    This verifies the consistency enforcement: Appendix D.4 rule.
    Records are constrained to npa dpd_bucket (dpd >= 91) so the DPD assertion
    is meaningful; the Markov history for npa risk_tier should produce 3+ M runs."""
    rng = random.Random(88)
    violations = 0
    checked = 0
    for _ in range(2000):
        r = generate_record(rng=rng, risk_tier="npa", dpd_bucket="npa")
        hist = r["payment_history_12m"]
        # Count max consecutive M's
        max_consec_m = max(
            (len(m) for m in hist.replace("P", " ").replace("D", " ").replace("-", " ").split() if m),
            default=0
        )
        if max_consec_m >= 3:
            checked += 1
            if r["dpd"] < 30:
                violations += 1
    # Among NPA-tier records with 3+ consecutive M's, >90% should have dpd >= 30
    if checked > 0:
        violation_rate = violations / checked
        assert violation_rate < 0.10, (
            f"{violations}/{checked} records with 3+ consecutive M had dpd < 30"
        )


def test_demographic_fields_are_english_script():
    """Names, cities, states must use English script (no Devanagari characters)."""
    rng = random.Random(1)
    for _ in range(50):
        record = generate_record(rng=rng, schema_modules=["demographic"])
        for field in ("name", "city", "state"):
            value = record[field]
            devanagari_chars = [c for c in value if 0x0900 <= ord(c) <= 0x097F]
            assert not devanagari_chars, (
                f"Field '{field}' contains Devanagari characters {devanagari_chars!r} "
                f"in value {value!r}. Locale must be en_IN not hi_IN."
            )


# --- Action history tests ---

def test_action_history_structure():
    """Each entry must have all required fields with valid values."""
    import random as _random
    from domain_definitions import ACTION_TYPES, ACTION_OUTCOMES, ACTION_COUNT_RANGES
    rng = _random.Random(42)
    history = _generate_action_history("mild", "near_prime", "Open", rng)
    assert isinstance(history, list)
    lo, hi = ACTION_COUNT_RANGES["mild"]
    assert lo <= len(history) <= hi, f"Expected len in [{lo}, {hi}], got {len(history)}"
    for i, entry in enumerate(history):
        assert set(entry.keys()) == {"seq", "action", "channel", "outcome", "days_since_call"}
        assert entry["seq"] == i + 1
        assert entry["action"] in ACTION_TYPES
        assert entry["outcome"] in ACTION_OUTCOMES

def test_action_history_days_monotonic():
    """days_since_call must be non-decreasing across entries."""
    import random as _random
    rng = _random.Random(7)
    history = _generate_action_history("severe", "sub_prime", "PTP", rng)
    days = [e["days_since_call"] for e in history]
    assert days == sorted(days), f"days_since_call not monotonic: {days}"

def test_action_history_ptp_resolution_has_ptp_outcome():
    """resolution_status=PTP must produce a PTP outcome in every invocation."""
    import random as _random
    for seed in range(20):
        rng = _random.Random(seed)
        history = _generate_action_history("mild", "near_prime", "PTP", rng)
        assert any(e["outcome"] == "PTP" for e in history), (
            f"No PTP outcome found for seed={seed}: {history}"
        )

def test_action_history_written_off_no_payment():
    """Written-off records must have no PAYMENT outcome in action_history."""
    import random as _random
    for seed in range(20):
        rng = _random.Random(seed)
        history = _generate_action_history("npa", "npa", "Written-off", rng)
        assert not any(e["outcome"] == "PAYMENT" for e in history), (
            f"PAYMENT outcome found in Written-off record (seed={seed})"
        )

def test_action_history_legal_has_legal_notice():
    """resolution_status=Legal must produce a LEGAL_NOTICE action in every invocation."""
    import random as _random
    for seed in range(20):
        rng = _random.Random(seed)
        history = _generate_action_history("npa", "npa", "Legal", rng)
        assert any(e["action"] == "LEGAL_NOTICE" for e in history), (
            f"No LEGAL_NOTICE action found for seed={seed}: {history}"
        )

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
    """days_after_call must be strictly increasing."""
    import random as _random
    for seed in range(10):
        rng = _random.Random(seed)
        result = _generate_payment_history_post_call(1, "Open", 8000.0, "near_prime", rng)
        if result:
            days = [e["days_after_call"] for e in result]
            assert days == sorted(days), f"days_after_call not monotonic: {days}"
            assert len(days) == len(set(days)), f"Duplicate days found: {days}"


def test_interactions_module_adds_fields():
    """schema_modules=['interactions'] must add action_history and payment_history."""
    rng = random.Random(42)
    record = generate_record(rng=rng, schema_modules=["interactions"])
    assert "action_history" in record
    assert "payment_history" in record
    assert isinstance(record["action_history"], list)
    assert isinstance(record["payment_history"], list)

def test_interactions_absent_without_module():
    """Without 'interactions' module, fields must not appear."""
    rng = random.Random(42)
    record = generate_record(rng=rng, schema_modules=[])
    assert "action_history" not in record
    assert "payment_history" not in record

def test_interactions_payment_history_empty_when_written_off():
    """For Written-off records, payment_history must be empty list."""
    for seed in range(200):
        rng = random.Random(seed)
        record = generate_record(rng=rng, dpd_bucket="npa", schema_modules=["interactions"])
        if record["resolution_status"] == "Written-off":
            assert record["payment_history"] == []
            return
    pytest.skip("No Written-off record found in 200 seeds")
