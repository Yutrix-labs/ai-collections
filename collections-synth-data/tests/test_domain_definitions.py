import pytest
from domain_definitions import (
    DPD_BUCKETS,
    RISK_TIERS,
    MARKOV_MATRICES,
    MARKOV_INIT,
    CIBIL_RANGES,
    RESOLUTION_DIST,
    CONTACT_ATTEMPTS_RANGES,
    OUTSTANDING_RANGES,
    LOAN_TYPES,
    SEGMENTS,
    STATE_CHARS,
    BASE_PAID_PROB,
    DEFAULT_DPD_WEIGHTS,
    DEFAULT_SEGMENT_WEIGHTS,
    DEFAULT_RISK_WEIGHTS,
)


def test_dpd_buckets_cover_all_ranges():
    """All DPD buckets exist with correct labels."""
    assert set(DPD_BUCKETS.keys()) == {"current", "early", "mild", "severe", "npa"}


def test_risk_tiers_exist():
    assert set(RISK_TIERS) == {"prime", "near_prime", "sub_prime", "npa"}


def test_markov_matrices_exist_for_all_tiers():
    for tier in RISK_TIERS:
        assert tier in MARKOV_MATRICES, f"Missing Markov matrix for {tier}"


def test_markov_rows_sum_to_one():
    """Each row in every transition matrix must sum to 1.0."""
    for tier, matrix in MARKOV_MATRICES.items():
        for from_state, transitions in matrix.items():
            total = sum(transitions.values())
            assert abs(total - 1.0) < 1e-6, (
                f"{tier}/{from_state} row sums to {total}, not 1.0"
            )


def test_markov_init_sums_to_one():
    for tier, dist in MARKOV_INIT.items():
        total = sum(dist.values())
        assert abs(total - 1.0) < 1e-6, f"{tier} init sums to {total}"


def test_cibil_ranges_are_valid():
    for bucket, (low, mode, high) in CIBIL_RANGES.items():
        assert 300 <= low < mode < high <= 900, (
            f"Bad CIBIL range for {bucket}: ({low}, {mode}, {high})"
        )


def test_resolution_dist_sums_to_100_per_bucket():
    for bucket, dist in RESOLUTION_DIST.items():
        total = sum(dist.values())
        assert total == 100, f"{bucket} resolution dist sums to {total}"


def test_state_chars_defined():
    assert set(STATE_CHARS) == {"P", "D", "M", "-"}


def test_outstanding_ranges_positive():
    for key, (lo, hi) in OUTSTANDING_RANGES.items():
        assert lo > 0 and hi > lo, f"Bad outstanding range for {key}"


def test_base_paid_prob_values_in_range():
    """All base probabilities must be in (0, 1)."""
    for tier, buckets in BASE_PAID_PROB.items():
        for bucket, prob in buckets.items():
            assert 0.0 < prob < 1.0, (
                f"BASE_PAID_PROB[{tier}][{bucket}]={prob} out of (0,1)"
            )


def test_base_paid_prob_covers_all_tiers_and_buckets():
    """Every tier x bucket combination must have a probability."""
    from domain_definitions import RISK_TIERS, DPD_BUCKETS
    for tier in RISK_TIERS:
        assert tier in BASE_PAID_PROB, f"Missing tier {tier} in BASE_PAID_PROB"
        for bucket in DPD_BUCKETS:
            assert bucket in BASE_PAID_PROB[tier], (
                f"Missing bucket {bucket} for tier {tier}"
            )


def test_default_segment_weights_sum_to_100():
    assert sum(DEFAULT_SEGMENT_WEIGHTS.values()) == 100


def test_default_risk_weights_sum_to_100_per_segment():
    for segment, weights in DEFAULT_RISK_WEIGHTS.items():
        total = sum(weights.values())
        assert total == 100, f"{segment} risk weights sum to {total}"


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
        assert sum(weights.values()) == 100, (
            f"Tier '{tier}' outcome weights sum to {sum(weights.values())}, not 100"
        )

def test_action_type_weights_sum_to_100_per_bucket():
    from domain_definitions import DPD_BUCKETS, ACTION_TYPE_WEIGHTS, ACTION_TYPES
    for bucket in DPD_BUCKETS:
        weights = ACTION_TYPE_WEIGHTS[bucket]
        assert sum(weights.values()) == 100, (
            f"Bucket '{bucket}' action type weights sum to {sum(weights.values())}, not 100"
        )

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
        assert sum(weights.values()) == 100, (
            f"Tier '{tier}' payment type weights sum to {sum(weights.values())}, not 100"
        )

def test_payment_channel_weights_sum_to_100_and_match_channels():
    from domain_definitions import PAYMENT_CHANNELS, PAYMENT_CHANNEL_WEIGHTS
    assert len(PAYMENT_CHANNEL_WEIGHTS) == len(PAYMENT_CHANNELS)
    assert sum(PAYMENT_CHANNEL_WEIGHTS) == 100

def test_action_channel_map_covers_all_action_types():
    from domain_definitions import ACTION_CHANNEL_MAP, ACTION_TYPES
    assert set(ACTION_CHANNEL_MAP.keys()) == set(ACTION_TYPES)
    assert all(isinstance(v, str) for v in ACTION_CHANNEL_MAP.values())
