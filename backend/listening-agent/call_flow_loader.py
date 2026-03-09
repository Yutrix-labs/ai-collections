"""
Call flow loader — loads call_flows.json once at import,
provides heuristic-based flow selection and text formatting.
"""

import json
from pathlib import Path

# Load flows once at module import
_FLOWS_PATH = Path(__file__).parent.parent / "call_flows.json"
_FLOWS: dict[str, dict] = {}

try:
    with open(_FLOWS_PATH, "r") as f:
        raw = json.load(f)
    for flow in raw.get("flows", []):
        _FLOWS[flow["id"]] = flow
except Exception as e:
    print(f"[CallFlowLoader] Failed to load call_flows.json: {e}")

# Hardship keywords for cant_pay_job_loss detection
_HARDSHIP_KEYWORDS = [
    "job loss",
    "lost job",
    "lost my job",
    "medical",
    "hospital",
    "health issue",
    "business loss",
    "business failed",
    "business closed",
    "financial crisis",
    "no income",
    "salary cut",
]

# Wrong number keywords
_WRONG_NUMBER_KEYWORDS = [
    "wrong number",
    "wrong person",
    "no such person",
    "not this person",
]


def select_flow(customer_profile: dict) -> str:
    """
    Select call flow based on customer data heuristics.
    Returns flow_id: 'ptp', 'wrong_number', or 'cant_pay_job_loss'.

    Priority:
    1. Past communications mention hardship → cant_pay_job_loss
    2. Past communications mention wrong number → wrong_number
    3. Default → ptp
    """
    past_comms = customer_profile.get("past_communications", [])

    for comm in past_comms:
        summary = (comm.get("summary") or "").lower()
        if any(kw in summary for kw in _HARDSHIP_KEYWORDS):
            return "cant_pay_job_loss"

    for comm in past_comms:
        summary = (comm.get("summary") or "").lower()
        if any(kw in summary for kw in _WRONG_NUMBER_KEYWORDS):
            return "wrong_number"

    return "ptp"


def format_flow_text(flow_id: str) -> str:
    """
    Format a call flow as plain text for the user prompt.
    Returns empty string if flow_id not found.
    """
    flow = _FLOWS.get(flow_id)
    if not flow:
        return ""

    steps = "\n".join(f"- {s}" for s in flow.get("steps", []))
    return f"Flow: {flow['name']}\nGoal: {flow['goal']}\nSteps:\n{steps}"


def get_flow_ids() -> list[str]:
    """Return all available flow IDs."""
    return list(_FLOWS.keys())
