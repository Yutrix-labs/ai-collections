from copilot_schema import (
    CopilotResponse,
    NextMove,
    Disposition,
    Priority,
    DispositionResult,
    NextActionType,
)
from pydantic import ValidationError
import json


def test_validation():
    # Test valid data with points-based next_move
    data = {
        "next_move": {"points": ["Confirm identity", "Reference loan account"], "priority": "high"},
        "disposition": {
            "result": "PTP",
            "confidence": 0.95,
            "date": "2026-02-21",
            "amount": 5000.0,
            "notes": "Customer committed to payment",
            "nextAction": "Follow-up Call",
        },
    }

    print("Testing validation with points-based next_move...")

    try:
        response = CopilotResponse.model_validate(data)
        print("✅ Validation successful!")
        print(f"Points: {response.next_move.points}")
        print(f"Priority: {response.next_move.priority.value}")
        print(f"Notes length: {len(response.disposition.notes)}")
    except ValidationError as e:
        print("❌ Validation failed!")
        print(e)
        exit(1)

    # Test truncation: point exceeding 50 chars should be truncated
    long_point = "A" * 60
    data2 = {
        "next_move": {"points": [long_point], "priority": "medium"},
        "disposition": None,
    }
    try:
        response2 = CopilotResponse.model_validate(data2)
        print(f"✅ Long point truncated to {len(response2.next_move.points[0])} chars")
    except ValidationError as e:
        print("❌ Long point validation failed!")
        print(e)
        exit(1)

    # Test failure: 3 points should fail (max 2)
    data3 = {
        "next_move": {"points": ["a", "b", "c"], "priority": "low"},
        "disposition": None,
    }
    try:
        CopilotResponse.model_validate(data3)
        print("❌ Validation should have failed for 3 points!")
        exit(1)
    except ValidationError:
        print("✅ Validation correctly failed for 3 points")

    # Test failure: empty points should fail
    data4 = {
        "next_move": {"points": [], "priority": "low"},
        "disposition": None,
    }
    try:
        CopilotResponse.model_validate(data4)
        print("❌ Validation should have failed for empty points!")
        exit(1)
    except ValidationError:
        print("✅ Validation correctly failed for empty points")


if __name__ == "__main__":
    test_validation()
