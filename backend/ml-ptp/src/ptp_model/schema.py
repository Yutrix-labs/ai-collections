"""Pydantic request/response models for the scoring API.

The request mirrors the raw account schema that the Spring Boot backend already holds.
Every field is optional so the service can score partial/live records — missing values
are handled by the feature pipeline (imputation / native NaN support).
"""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


class AccountFeatures(BaseModel):
    """Raw account features as sent by the backend (one PTP-given account)."""

    account_id: Optional[str] = None

    # Delinquency
    latest_dpd: Optional[float] = None
    dpd_bucket_0_30: Optional[float] = None
    dpd_bucket_30_60: Optional[float] = None
    dpd_bucket_60_90: Optional[float] = None
    dpd_bucket_90_120: Optional[float] = None
    npa_flag: Optional[int] = None

    # Loan / financial
    segment: Optional[str] = None
    loan_type: Optional[str] = None
    loan_amount: Optional[float] = None
    outstanding_amount: Optional[float] = None
    collateral_type: Optional[str] = None
    ltv_ratio: Optional[float] = None
    forced_sale_value: Optional[float] = None

    # Demographics
    age_group: Optional[str] = None
    income_band: Optional[str] = None
    employer_type: Optional[str] = None
    city_tier: Optional[str] = None

    # Credit risk
    cibil_score: Optional[float] = None
    internal_score: Optional[float] = None
    bureau_enquiries_6m: Optional[float] = None
    active_loans: Optional[float] = None
    credit_utilization_pct: Optional[float] = None

    # Engagement / behavioral
    total_interactions: Optional[float] = None
    action_history: Optional[str] = None
    last_contact_channel: Optional[str] = None
    days_since_last_contact: Optional[float] = None
    response_rate: Optional[float] = None
    call_pickup_rate: Optional[float] = None
    payment_history: Optional[str] = None
    broken_ptp_count: Optional[float] = None
    avg_days_to_pay: Optional[float] = None
    escalation_flag: Optional[int] = None

    # Contactability / preference
    preferred_channel: Optional[str] = None
    language_preference: Optional[str] = None
    whatsapp_opted_in: Optional[int] = None
    do_not_disturb: Optional[int] = None
    best_time_to_call: Optional[str] = None

    model_config = {"extra": "ignore"}


class Factor(BaseModel):
    """A single human-readable driver behind the prediction."""

    feature: str
    label: str
    value: Optional[float | str] = None
    impact: str = Field(description="positive | negative — direction of influence on fulfillment")


class SubScore(BaseModel):
    """A secondary probability score (e.g. payment within N days) with its band."""

    probability: float = Field(description="Probability 0-1")
    band: str = Field(description="High / Medium / Low likelihood band")


class PTPPrediction(BaseModel):
    account_id: Optional[str] = None
    probability: float = Field(description="Calibrated P(PTP fulfilled), 0-1")
    fulfilled: bool = Field(description="probability >= decision threshold")
    band: str = Field(description="High / Medium / Low likelihood band")
    threshold: float
    top_factors: list[Factor]
    payment_probability_15d: Optional[SubScore] = Field(
        default=None, description="P(pays within 15 days)"
    )
    payment_probability_30d: Optional[SubScore] = Field(
        default=None, description="P(pays within 30 days)"
    )
    model_version: str


class BatchRequest(BaseModel):
    accounts: list[AccountFeatures]


class BatchResponse(BaseModel):
    predictions: list[PTPPrediction]
