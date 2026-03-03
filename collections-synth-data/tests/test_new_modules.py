"""
tests/test_new_modules.py
TDD tests for the three new schema modules: behavioural, communication, collateral.
Written BEFORE implementation — all tests must fail initially.
"""

import random
import pytest
from phase1_faker_generator import (
    generate_record,
    _generate_behavioural_fields,
    _generate_communication_fields,
    _generate_collateral_fields,
)
from domain_definitions import (
    BEHAVIOURAL_RESPONSE_RATES,
    BEHAVIOURAL_ESCALATION_RATES,
    BEHAVIOURAL_SELF_CURE_PROBS,
    COMMUNICATION_CHANNELS,
    COMMUNICATION_TIME_WINDOWS,
    COMMUNICATION_LANGUAGES,
    COLLATERAL_BY_LOAN_TYPE,
    COLLATERAL_CONDITION_WEIGHTS,
)


# ══════════════════════════════════════════════════════════════════════════════
# BEHAVIOURAL MODULE
# ══════════════════════════════════════════════════════════════════════════════

BEHAVIOURAL_FIELDS = {
    "response_rate", "avg_days_to_respond", "self_cure_probability",
    "call_pickup_rate", "escalation_flag",
}


class TestBehaviouralModulePresence:
    def test_fields_present_when_module_enabled(self):
        rng = random.Random(1)
        record = generate_record(rng=rng, schema_modules=["behavioural"])
        for f in BEHAVIOURAL_FIELDS:
            assert f in record, f"Missing behavioural field: {f}"

    def test_fields_absent_without_module(self):
        rng = random.Random(1)
        record = generate_record(rng=rng, schema_modules=[])
        for f in BEHAVIOURAL_FIELDS:
            assert f not in record, f"Unexpected field present without module: {f}"


class TestBehaviouralFieldTypes:
    def test_response_rate_is_float_between_0_and_1(self):
        rng = random.Random(10)
        for _ in range(100):
            r = _generate_behavioural_fields("prime", "current", rng)
            v = r["response_rate"]
            assert isinstance(v, float), f"response_rate type {type(v)}"
            assert 0.0 <= v <= 1.0, f"response_rate={v} out of [0,1]"

    def test_avg_days_to_respond_is_positive_float(self):
        rng = random.Random(11)
        for _ in range(100):
            r = _generate_behavioural_fields("near_prime", "early", rng)
            v = r["avg_days_to_respond"]
            assert isinstance(v, float), f"avg_days_to_respond type {type(v)}"
            assert v > 0, f"avg_days_to_respond={v} must be positive"

    def test_self_cure_probability_is_float_between_0_and_1(self):
        rng = random.Random(12)
        for _ in range(100):
            r = _generate_behavioural_fields("sub_prime", "mild", rng)
            v = r["self_cure_probability"]
            assert isinstance(v, float)
            assert 0.0 <= v <= 1.0, f"self_cure_probability={v} out of [0,1]"

    def test_call_pickup_rate_is_float_between_0_and_1(self):
        rng = random.Random(13)
        for _ in range(100):
            r = _generate_behavioural_fields("npa", "npa", rng)
            v = r["call_pickup_rate"]
            assert isinstance(v, float)
            assert 0.0 <= v <= 1.0, f"call_pickup_rate={v} out of [0,1]"

    def test_escalation_flag_is_bool(self):
        rng = random.Random(14)
        for _ in range(100):
            r = _generate_behavioural_fields("sub_prime", "severe", rng)
            assert isinstance(r["escalation_flag"], bool)


class TestBehaviouralBusinessRules:
    def test_prime_has_higher_response_rate_than_npa(self):
        """Prime borrowers respond to contact more often than NPA borrowers."""
        rng_p = random.Random(42)
        prime_avg = sum(
            _generate_behavioural_fields("prime", "current", rng_p)["response_rate"]
            for _ in range(500)
        ) / 500

        rng_n = random.Random(42)
        npa_avg = sum(
            _generate_behavioural_fields("npa", "npa", rng_n)["response_rate"]
            for _ in range(500)
        ) / 500

        assert prime_avg > npa_avg, (
            f"Prime response_rate avg {prime_avg:.3f} <= NPA {npa_avg:.3f}"
        )

    def test_npa_dpd_has_higher_escalation_rate_than_current(self):
        """NPA accounts should escalate more often than current accounts."""
        rng = random.Random(77)
        npa_escalations = sum(
            _generate_behavioural_fields("sub_prime", "npa", rng)["escalation_flag"]
            for _ in range(500)
        )
        current_escalations = sum(
            _generate_behavioural_fields("prime", "current", rng)["escalation_flag"]
            for _ in range(500)
        )
        assert npa_escalations > current_escalations, (
            f"NPA escalations={npa_escalations} <= current={current_escalations}"
        )

    def test_prime_current_has_highest_self_cure(self):
        """Prime/current accounts most likely to self-cure without agent contact."""
        rng_best = random.Random(88)
        best_avg = sum(
            _generate_behavioural_fields("prime", "current", rng_best)["self_cure_probability"]
            for _ in range(300)
        ) / 300

        rng_worst = random.Random(88)
        worst_avg = sum(
            _generate_behavioural_fields("npa", "npa", rng_worst)["self_cure_probability"]
            for _ in range(300)
        ) / 300

        assert best_avg > worst_avg, (
            f"prime/current self_cure avg {best_avg:.3f} <= npa/npa {worst_avg:.3f}"
        )

    def test_generate_record_passes_correct_args_to_behavioural(self):
        """generate_record with behavioural module must produce valid field values."""
        rng = random.Random(99)
        for _ in range(50):
            r = generate_record(rng=rng, schema_modules=["behavioural"])
            assert 0.0 <= r["response_rate"] <= 1.0
            assert r["avg_days_to_respond"] > 0
            assert isinstance(r["escalation_flag"], bool)


# ══════════════════════════════════════════════════════════════════════════════
# COMMUNICATION MODULE
# ══════════════════════════════════════════════════════════════════════════════

COMMUNICATION_FIELDS = {
    "preferred_channel", "contact_time_window", "language_preference",
    "whatsapp_opted_in", "do_not_disturb", "email_deliverable",
}


class TestCommunicationModulePresence:
    def test_fields_present_when_module_enabled(self):
        rng = random.Random(2)
        record = generate_record(rng=rng, schema_modules=["communication"])
        for f in COMMUNICATION_FIELDS:
            assert f in record, f"Missing communication field: {f}"

    def test_fields_absent_without_module(self):
        rng = random.Random(2)
        record = generate_record(rng=rng, schema_modules=[])
        for f in COMMUNICATION_FIELDS:
            assert f not in record, f"Unexpected field present: {f}"


class TestCommunicationFieldTypes:
    def test_preferred_channel_is_valid(self):
        rng = random.Random(20)
        for _ in range(100):
            r = _generate_communication_fields("prime", "Metro", rng)
            assert r["preferred_channel"] in COMMUNICATION_CHANNELS, (
                f"Invalid channel: {r['preferred_channel']}"
            )

    def test_contact_time_window_is_valid(self):
        rng = random.Random(21)
        for _ in range(100):
            r = _generate_communication_fields("near_prime", "Tier-1", rng)
            assert r["contact_time_window"] in COMMUNICATION_TIME_WINDOWS, (
                f"Invalid window: {r['contact_time_window']}"
            )

    def test_language_preference_is_valid(self):
        rng = random.Random(22)
        for _ in range(100):
            r = _generate_communication_fields("sub_prime", "Tier-2", rng)
            assert r["language_preference"] in COMMUNICATION_LANGUAGES, (
                f"Invalid language: {r['language_preference']}"
            )

    def test_boolean_fields_are_bool(self):
        rng = random.Random(23)
        for _ in range(100):
            r = _generate_communication_fields("npa", "Rural", rng)
            assert isinstance(r["whatsapp_opted_in"], bool)
            assert isinstance(r["do_not_disturb"], bool)
            assert isinstance(r["email_deliverable"], bool)


class TestCommunicationBusinessRules:
    def test_npa_has_higher_dnd_rate_than_prime(self):
        """NPA borrowers more likely to be on DND registry."""
        rng_p = random.Random(42)
        prime_dnd = sum(
            _generate_communication_fields("prime", "Metro", rng_p)["do_not_disturb"]
            for _ in range(500)
        )
        rng_n = random.Random(42)
        npa_dnd = sum(
            _generate_communication_fields("npa", "Metro", rng_n)["do_not_disturb"]
            for _ in range(500)
        )
        assert npa_dnd > prime_dnd, (
            f"NPA DND count {npa_dnd} <= prime {prime_dnd}"
        )

    def test_metro_has_higher_whatsapp_optin_than_rural(self):
        """Metro borrowers more likely to have WhatsApp opted in."""
        rng_m = random.Random(55)
        metro_optin = sum(
            _generate_communication_fields("near_prime", "Metro", rng_m)["whatsapp_opted_in"]
            for _ in range(500)
        )
        rng_r = random.Random(55)
        rural_optin = sum(
            _generate_communication_fields("near_prime", "Rural", rng_r)["whatsapp_opted_in"]
            for _ in range(500)
        )
        assert metro_optin > rural_optin, (
            f"Metro whatsapp_opted_in {metro_optin} <= Rural {rural_optin}"
        )

    def test_npa_has_lower_email_deliverable_rate(self):
        """NPA accounts more likely to have stale/undeliverable emails."""
        rng_p = random.Random(66)
        prime_del = sum(
            _generate_communication_fields("prime", "Metro", rng_p)["email_deliverable"]
            for _ in range(500)
        )
        rng_n = random.Random(66)
        npa_del = sum(
            _generate_communication_fields("npa", "Rural", rng_n)["email_deliverable"]
            for _ in range(500)
        )
        assert prime_del > npa_del, (
            f"Prime email_deliverable {prime_del} <= NPA {npa_del}"
        )

    def test_generate_record_communication_valid(self):
        """generate_record with communication module produces valid field values."""
        rng = random.Random(99)
        for _ in range(50):
            r = generate_record(rng=rng, schema_modules=["communication"])
            assert r["preferred_channel"] in COMMUNICATION_CHANNELS
            assert r["contact_time_window"] in COMMUNICATION_TIME_WINDOWS
            assert isinstance(r["whatsapp_opted_in"], bool)


# ══════════════════════════════════════════════════════════════════════════════
# COLLATERAL MODULE
# ══════════════════════════════════════════════════════════════════════════════

COLLATERAL_FIELDS = {
    "collateral_type", "collateral_value", "ltv_ratio",
    "collateral_condition", "encumbrance_status", "forced_sale_value",
}
UNSECURED_LOAN_TYPES = {"Personal", "Credit Card"}
SECURED_LOAN_TYPES   = {"Home", "Auto", "Gold", "MSME"}


class TestCollateralModulePresence:
    def test_fields_present_when_module_enabled(self):
        rng = random.Random(3)
        record = generate_record(rng=rng, schema_modules=["collateral"])
        for f in COLLATERAL_FIELDS:
            assert f in record, f"Missing collateral field: {f}"

    def test_fields_absent_without_module(self):
        rng = random.Random(3)
        record = generate_record(rng=rng, schema_modules=[])
        for f in COLLATERAL_FIELDS:
            assert f not in record, f"Unexpected field present: {f}"


class TestCollateralFieldTypes:
    def test_collateral_type_is_valid_string(self):
        rng = random.Random(30)
        valid_types = set(COLLATERAL_BY_LOAN_TYPE.values())
        for _ in range(100):
            r = _generate_collateral_fields("Home", 500_000.0, "prime", rng)
            assert r["collateral_type"] in valid_types, (
                f"Invalid collateral_type: {r['collateral_type']}"
            )

    def test_collateral_value_is_non_negative_float(self):
        rng = random.Random(31)
        for loan_type in ["Home", "Auto", "Personal", "Gold"]:
            for _ in range(20):
                r = _generate_collateral_fields(loan_type, 200_000.0, "near_prime", rng)
                assert isinstance(r["collateral_value"], float)
                assert r["collateral_value"] >= 0.0, (
                    f"collateral_value={r['collateral_value']} negative for {loan_type}"
                )

    def test_ltv_ratio_is_non_negative_float(self):
        rng = random.Random(32)
        for _ in range(100):
            r = _generate_collateral_fields("Auto", 300_000.0, "sub_prime", rng)
            assert isinstance(r["ltv_ratio"], float)
            assert r["ltv_ratio"] >= 0.0

    def test_collateral_condition_is_valid(self):
        rng = random.Random(33)
        valid = set(COLLATERAL_CONDITION_WEIGHTS.keys())
        for _ in range(100):
            r = _generate_collateral_fields("Home", 1_000_000.0, "prime", rng)
            assert r["collateral_condition"] in valid, (
                f"Invalid condition: {r['collateral_condition']}"
            )

    def test_encumbrance_status_is_bool(self):
        rng = random.Random(34)
        for _ in range(100):
            r = _generate_collateral_fields("Home", 500_000.0, "near_prime", rng)
            assert isinstance(r["encumbrance_status"], bool)

    def test_forced_sale_value_is_non_negative_float(self):
        rng = random.Random(35)
        for _ in range(100):
            r = _generate_collateral_fields("Gold", 150_000.0, "sub_prime", rng)
            assert isinstance(r["forced_sale_value"], float)
            assert r["forced_sale_value"] >= 0.0


class TestCollateralBusinessRules:
    def test_unsecured_loans_have_zero_collateral_value(self):
        """Personal and Credit Card loans are unsecured — collateral_value = 0."""
        rng = random.Random(42)
        for loan_type in UNSECURED_LOAN_TYPES:
            for _ in range(50):
                r = _generate_collateral_fields(loan_type, 100_000.0, "prime", rng)
                assert r["collateral_value"] == 0.0, (
                    f"{loan_type} collateral_value={r['collateral_value']} should be 0"
                )

    def test_unsecured_loans_have_zero_ltv(self):
        """Unsecured loans have no collateral → LTV ratio = 0."""
        rng = random.Random(43)
        for loan_type in UNSECURED_LOAN_TYPES:
            for _ in range(50):
                r = _generate_collateral_fields(loan_type, 100_000.0, "prime", rng)
                assert r["ltv_ratio"] == 0.0, (
                    f"{loan_type} ltv_ratio={r['ltv_ratio']} should be 0"
                )

    def test_secured_loans_have_positive_collateral_value(self):
        """Secured loan types must have positive collateral_value."""
        rng = random.Random(44)
        for loan_type in SECURED_LOAN_TYPES:
            for _ in range(50):
                r = _generate_collateral_fields(loan_type, 500_000.0, "prime", rng)
                assert r["collateral_value"] > 0.0, (
                    f"{loan_type} collateral_value={r['collateral_value']} should be > 0"
                )

    def test_forced_sale_value_leq_collateral_value(self):
        """Forced sale value must never exceed collateral value (it's a haircut)."""
        rng = random.Random(45)
        for _ in range(200):
            r = _generate_collateral_fields("Home", 800_000.0, "near_prime", rng)
            assert r["forced_sale_value"] <= r["collateral_value"], (
                f"forced_sale_value={r['forced_sale_value']} > "
                f"collateral_value={r['collateral_value']}"
            )

    def test_npa_has_higher_ltv_than_prime(self):
        """NPA accounts carry higher LTV ratios — riskier relative to collateral."""
        rng_p = random.Random(55)
        prime_ltv = sum(
            _generate_collateral_fields("Home", 500_000.0, "prime", rng_p)["ltv_ratio"]
            for _ in range(300)
        ) / 300

        rng_n = random.Random(55)
        npa_ltv = sum(
            _generate_collateral_fields("Home", 500_000.0, "npa", rng_n)["ltv_ratio"]
            for _ in range(300)
        ) / 300

        assert npa_ltv > prime_ltv, (
            f"NPA avg LTV {npa_ltv:.3f} <= prime avg LTV {prime_ltv:.3f}"
        )

    def test_npa_has_worse_collateral_condition(self):
        """NPA accounts should have more 'Poor' condition collateral than prime."""
        rng_p = random.Random(66)
        prime_poor = sum(
            1 for _ in range(300)
            if _generate_collateral_fields("Home", 500_000.0, "prime", rng_p)["collateral_condition"] == "Poor"
        )
        rng_n = random.Random(66)
        npa_poor = sum(
            1 for _ in range(300)
            if _generate_collateral_fields("Home", 500_000.0, "npa", rng_n)["collateral_condition"] == "Poor"
        )
        assert npa_poor > prime_poor, (
            f"NPA 'Poor' count {npa_poor} <= prime {prime_poor}"
        )

    def test_home_loan_maps_to_property_collateral(self):
        rng = random.Random(77)
        for _ in range(20):
            r = _generate_collateral_fields("Home", 1_000_000.0, "prime", rng)
            assert r["collateral_type"] == "Property"

    def test_auto_loan_maps_to_vehicle_collateral(self):
        rng = random.Random(78)
        for _ in range(20):
            r = _generate_collateral_fields("Auto", 400_000.0, "prime", rng)
            assert r["collateral_type"] == "Vehicle"

    def test_gold_loan_maps_to_gold_collateral(self):
        rng = random.Random(79)
        for _ in range(20):
            r = _generate_collateral_fields("Gold", 200_000.0, "prime", rng)
            assert r["collateral_type"] == "Gold"

    def test_generate_record_collateral_valid(self):
        """generate_record with collateral module produces valid field values."""
        rng = random.Random(99)
        for _ in range(50):
            r = generate_record(rng=rng, schema_modules=["collateral"])
            assert r["collateral_value"] >= 0.0
            assert r["ltv_ratio"] >= 0.0
            assert r["forced_sale_value"] <= r["collateral_value"]
            assert isinstance(r["encumbrance_status"], bool)
