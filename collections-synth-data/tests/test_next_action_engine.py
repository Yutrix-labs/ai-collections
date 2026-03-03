"""
tests/test_next_action_engine.py
TDD tests for the suggested_next_action rules-based engine.
Written before implementation (red phase).
"""

import pytest
from next_action_engine import suggested_next_action


# ---------------------------------------------------------------------------
# Helpers — minimal record builders
# ---------------------------------------------------------------------------

def _core(overrides: dict | None = None) -> dict:
    """Minimal core-only record (no optional modules)."""
    base = {
        "risk_tier":        "prime",
        "dpd_bucket":       "current",
        "dpd":              0,
        "resolution_status": "Open",
        "contact_attempts": 2,
        "promise_to_pay":   False,
        "payment_history_12m": "PPPPPPPPPPPP",
    }
    if overrides:
        base.update(overrides)
    return base


def _full(overrides: dict | None = None) -> dict:
    """Core + all optional module fields at safe defaults."""
    base = _core()
    # behavioural
    base.update({
        "self_cure_probability": 0.50,
        "response_rate":         0.70,
        "call_pickup_rate":      0.70,
        "escalation_flag":       False,
    })
    # communication
    base.update({
        "do_not_disturb":   False,
        "whatsapp_opted_in": True,
        "email_deliverable": True,
        "preferred_channel": "phone",
    })
    # collateral
    base.update({
        "collateral_value": 500_000.0,
        "ltv_ratio":        0.60,
        "forced_sale_value": 300_000.0,
        "collateral_condition": "Good",
    })
    # interactions (last action)
    base["action_history"] = [
        {"seq": 1, "action": "CALL", "channel": "phone", "outcome": "CALLBACK", "days_since_call": 3}
    ]
    if overrides:
        base.update(overrides)
    return base


# ---------------------------------------------------------------------------
# TestHardRules
# ---------------------------------------------------------------------------

class TestHardRules:
    def test_written_off_returns_close_account(self):
        r = _core({"resolution_status": "Written-off"})
        result = suggested_next_action(r)
        assert result["next_action"] == "CLOSE_ACCOUNT"
        assert result["confidence"] >= 0.95

    def test_settled_returns_close_account(self):
        r = _core({"resolution_status": "Settled"})
        result = suggested_next_action(r)
        assert result["next_action"] == "CLOSE_ACCOUNT"
        assert result["confidence"] >= 0.95

    def test_dnd_returns_monitor(self):
        r = _full({"do_not_disturb": True, "resolution_status": "Open"})
        result = suggested_next_action(r)
        assert result["next_action"] == "MONITOR"

    def test_legal_status_returns_send_legal_notice(self):
        r = _core({"resolution_status": "Legal"})
        result = suggested_next_action(r)
        assert result["next_action"] == "SEND_LEGAL_NOTICE"
        assert result["confidence"] >= 0.90

    def test_npa_high_contacts_escalation_returns_legal(self):
        r = _full({
            "risk_tier":         "npa",
            "dpd_bucket":        "npa",
            "dpd":               120,
            "resolution_status": "Open",
            "contact_attempts":  16,
            "escalation_flag":   True,
        })
        result = suggested_next_action(r)
        assert result["next_action"] == "SEND_LEGAL_NOTICE"

    def test_ptp_plus_promise_to_pay_current_returns_monitor(self):
        r = _core({
            "resolution_status": "PTP",
            "promise_to_pay":    True,
            "dpd_bucket":        "current",
        })
        result = suggested_next_action(r)
        assert result["next_action"] == "MONITOR"

    def test_high_self_cure_current_returns_monitor(self):
        r = _full({
            "self_cure_probability": 0.75,
            "dpd_bucket":            "current",
            "resolution_status":     "Open",
        })
        result = suggested_next_action(r)
        assert result["next_action"] == "MONITOR"

    def test_ptp_status_mild_dpd_returns_call_back(self):
        r = _core({
            "resolution_status": "PTP",
            "dpd_bucket":        "mild",
            "promise_to_pay":    False,
        })
        result = suggested_next_action(r)
        assert result["next_action"] == "CALL_BACK"

    def test_zero_contact_prime_current_returns_monitor(self):
        r = _core({
            "contact_attempts": 0,
            "dpd_bucket":       "current",
            "risk_tier":        "prime",
        })
        result = suggested_next_action(r)
        assert result["next_action"] == "MONITOR"

    def test_zero_contact_npa_current_returns_send_sms(self):
        r = _core({
            "contact_attempts": 0,
            "dpd_bucket":       "current",
            "risk_tier":        "npa",
        })
        result = suggested_next_action(r)
        assert result["next_action"] == "SEND_SMS"


# ---------------------------------------------------------------------------
# TestScoringSignals
# ---------------------------------------------------------------------------

class TestScoringSignals:
    def test_npa_tier_severe_dpd_escalates(self):
        """NPA risk + severe DPD + poor engagement should produce an escalated action."""
        r = _full({
            "risk_tier":           "npa",
            "dpd_bucket":          "severe",
            "dpd":                 75,
            "resolution_status":   "Open",
            "contact_attempts":    5,
            # realistic signals for a non-responsive NPA/severe account
            "payment_history_12m": "MMMMMMMMMMMM",
            "response_rate":       0.10,
            "call_pickup_rate":    0.08,
            "self_cure_probability": 0.02,
            "action_history": [
                {"seq": 1, "action": "CALL", "channel": "phone", "outcome": "NO_RESPONSE", "days_since_call": 5}
            ],
        })
        result = suggested_next_action(r)
        assert result["next_action"] in {"FIELD_VISIT", "SEND_LEGAL_NOTICE", "OFFER_SETTLEMENT"}

    def test_prime_current_dpd_light_touch(self):
        """Prime tier + current DPD should recommend light-touch action."""
        r = _full({
            "risk_tier":        "prime",
            "dpd_bucket":       "current",
            "dpd":              0,
            "resolution_status": "Open",
            "contact_attempts": 1,
            "self_cure_probability": 0.40,
        })
        result = suggested_next_action(r)
        assert result["next_action"] in {"MONITOR", "SEND_SMS", "SEND_WHATSAPP", "CALL_BACK"}

    def test_ppp_history_lighter_action(self):
        """Three consecutive payments should lean toward lighter actions."""
        r = _full({
            "payment_history_12m": "PPPPPPPPPPPP",
            "dpd_bucket":          "early",
            "risk_tier":           "near_prime",
            "resolution_status":   "Open",
            "contact_attempts":    2,
            "self_cure_probability": 0.35,
        })
        result = suggested_next_action(r)
        # Should not escalate to legal/field on PPP history with early DPD
        assert result["next_action"] not in {"SEND_LEGAL_NOTICE", "FIELD_VISIT"}

    def test_mmm_history_escalation(self):
        """Three consecutive missed payments should push toward escalation."""
        r = _full({
            "payment_history_12m": "MMMMMMMMMMMM",
            "dpd_bucket":          "severe",
            "risk_tier":           "sub_prime",
            "resolution_status":   "Open",
            "contact_attempts":    8,
            "self_cure_probability": 0.05,
        })
        result = suggested_next_action(r)
        assert result["next_action"] in {
            "FIELD_VISIT", "SEND_LEGAL_NOTICE", "OFFER_SETTLEMENT", "CALL_BACK"
        }


# ---------------------------------------------------------------------------
# TestChannelSelection
# ---------------------------------------------------------------------------

class TestChannelSelection:
    def test_whatsapp_opted_in_can_use_whatsapp(self):
        """If whatsapp_opted_in, whatsapp may be selected as channel."""
        r = _full({
            "whatsapp_opted_in": True,
            "dpd_bucket":        "early",
            "risk_tier":         "near_prime",
            "resolution_status": "Open",
            "contact_attempts":  1,
            "self_cure_probability": 0.20,
        })
        result = suggested_next_action(r)
        # For SEND_WHATSAPP action the channel should be whatsapp
        if result["next_action"] == "SEND_WHATSAPP":
            assert result["channel"] == "whatsapp"

    def test_monitor_has_no_channel(self):
        r = _full({
            "self_cure_probability": 0.75,
            "dpd_bucket":            "current",
            "resolution_status":     "Open",
        })
        result = suggested_next_action(r)
        if result["next_action"] == "MONITOR":
            assert result["channel"] is None

    def test_close_account_has_no_channel(self):
        r = _core({"resolution_status": "Written-off"})
        result = suggested_next_action(r)
        assert result["channel"] is None

    def test_field_visit_channel_is_field(self):
        r = _full({
            "risk_tier":        "npa",
            "dpd_bucket":       "npa",
            "dpd":              120,
            "resolution_status": "Open",
            "contact_attempts": 8,
            "call_pickup_rate": 0.05,
            "response_rate":    0.05,
            "payment_history_12m": "MMMMMMMMMMMM",
            "self_cure_probability": 0.01,
            "collateral_value": 1_000_000.0,
            "ltv_ratio":        0.70,
            "collateral_condition": "Good",
        })
        result = suggested_next_action(r)
        if result["next_action"] == "FIELD_VISIT":
            assert result["channel"] == "field"

    def test_send_sms_action_channel_is_sms(self):
        r = _core({
            "contact_attempts": 0,
            "dpd_bucket":       "current",
            "risk_tier":        "sub_prime",
        })
        result = suggested_next_action(r)
        if result["next_action"] == "SEND_SMS":
            assert result["channel"] == "sms"


# ---------------------------------------------------------------------------
# TestOutputStructure
# ---------------------------------------------------------------------------

class TestOutputStructure:
    def test_required_keys_present(self):
        r = _core()
        result = suggested_next_action(r)
        for key in ("next_action", "channel", "reason", "priority", "confidence", "action_scores"):
            assert key in result, f"Missing key: {key}"

    def test_confidence_in_range(self):
        r = _core()
        result = suggested_next_action(r)
        assert 0.0 <= result["confidence"] <= 1.0

    def test_priority_is_valid(self):
        r = _core()
        result = suggested_next_action(r)
        assert result["priority"] in {"HIGH", "MEDIUM", "LOW"}

    def test_reason_is_non_empty_string(self):
        r = _core()
        result = suggested_next_action(r)
        assert isinstance(result["reason"], str) and len(result["reason"]) > 0

    def test_next_action_is_valid_string(self):
        from domain_definitions import NEXT_ACTIONS
        r = _core()
        result = suggested_next_action(r)
        assert result["next_action"] in NEXT_ACTIONS

    def test_action_scores_is_dict(self):
        r = _core()
        result = suggested_next_action(r)
        assert isinstance(result["action_scores"], dict)
        assert len(result["action_scores"]) > 0


# ---------------------------------------------------------------------------
# TestModuleGraceDegradation
# ---------------------------------------------------------------------------

class TestModuleGraceDegradation:
    def test_core_fields_only(self):
        """Engine works with just the core record fields (no optional modules)."""
        r = _core()
        result = suggested_next_action(r)
        assert result["next_action"] is not None
        assert isinstance(result["reason"], str)

    def test_all_modules_present(self):
        """Engine works when all module fields are present."""
        r = _full()
        result = suggested_next_action(r)
        assert result["next_action"] is not None

    def test_partial_modules_behavioural_only(self):
        """Engine works with only behavioural fields added."""
        r = _core()
        r["self_cure_probability"] = 0.30
        r["response_rate"]         = 0.50
        r["call_pickup_rate"]      = 0.50
        r["escalation_flag"]       = False
        result = suggested_next_action(r)
        assert result["next_action"] is not None

    def test_partial_modules_communication_only(self):
        """Engine works with only communication fields added."""
        r = _core()
        r["do_not_disturb"]    = False
        r["whatsapp_opted_in"] = True
        r["email_deliverable"] = True
        r["preferred_channel"] = "whatsapp"
        result = suggested_next_action(r)
        assert result["next_action"] is not None

    def test_partial_modules_collateral_only(self):
        """Engine works with only collateral fields added."""
        r = _core()
        r["collateral_value"]   = 200_000.0
        r["ltv_ratio"]          = 0.55
        r["forced_sale_value"]  = 130_000.0
        r["collateral_condition"] = "Good"
        result = suggested_next_action(r)
        assert result["next_action"] is not None

    def test_missing_action_history_ok(self):
        """Engine works when action_history key is absent."""
        r = _full()
        r.pop("action_history", None)
        result = suggested_next_action(r)
        assert result["next_action"] is not None

    def test_empty_action_history_ok(self):
        """Engine works when action_history is an empty list."""
        r = _full()
        r["action_history"] = []
        result = suggested_next_action(r)
        assert result["next_action"] is not None


# ---------------------------------------------------------------------------
# TestWiringIntoRecord
# ---------------------------------------------------------------------------

class TestWiringIntoRecord:
    def test_generate_record_with_next_action_module(self):
        """generate_record with 'next_action' in schema_modules adds 5 fields."""
        from phase1_faker_generator import generate_record
        import random
        rng = random.Random(99)
        record = generate_record(rng=rng, schema_modules=["next_action"])
        expected_fields = [
            "suggested_next_action",
            "next_action_channel",
            "next_action_reason",
            "next_action_priority",
            "next_action_confidence",
        ]
        for field in expected_fields:
            assert field in record, f"Missing field: {field}"

    def test_generate_record_next_action_values_valid(self):
        """All wired fields have correct types / value ranges."""
        from phase1_faker_generator import generate_record
        from domain_definitions import NEXT_ACTIONS
        import random
        rng = random.Random(77)
        record = generate_record(rng=rng, schema_modules=["next_action"])
        assert record["suggested_next_action"] in NEXT_ACTIONS
        assert record["next_action_priority"] in {"HIGH", "MEDIUM", "LOW"}
        assert 0.0 <= record["next_action_confidence"] <= 1.0
        assert isinstance(record["next_action_reason"], str)

    def test_generate_record_all_modules_with_next_action(self):
        """next_action module works when combined with all other modules."""
        from phase1_faker_generator import generate_record
        import random
        rng = random.Random(55)
        record = generate_record(
            rng=rng,
            schema_modules=[
                "demographic", "bureau", "interactions",
                "behavioural", "communication", "collateral", "next_action"
            ]
        )
        assert "suggested_next_action" in record
        assert "next_action_reason" in record
