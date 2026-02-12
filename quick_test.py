"""
Quick test script for AI Collections Assistant Backend.
Run this after starting the FastAPI server.
"""

import requests
import time

BASE_URL = "http://localhost:8000"
CALL_ID = "test-call-001"


def test_health():
    """Test health endpoint."""
    print("1. Testing health endpoint...")
    response = requests.get(f"{BASE_URL}/health")
    print(f"   Status: {response.status_code}")
    print(f"   Response: {response.json()}")
    assert response.status_code == 200
    print("   ✅ Health check passed\n")


def test_get_context():
    """Test get call context."""
    print("2. Testing GET call context...")
    response = requests.get(f"{BASE_URL}/api/v1/calls/{CALL_ID}/context")
    print(f"   Status: {response.status_code}")

    if response.status_code == 200:
        data = response.json()
        print(f"   Customer: {data['customer']['name']}")
        print(f"   DPD: {data['additional']['dpd']} days")
        print(f"   Initial insights: {len(data['initial_insights'])}")
        print("   ✅ Context retrieved\n")
    else:
        print(f"   ❌ Error: {response.text}\n")


def test_add_utterances():
    """Test adding utterances."""
    print("3. Testing add utterances...")

    utterances = [
        {
            "call_id": CALL_ID,
            "speaker": "agent",
            "text": "Good morning, am I speaking with Mr. Rajesh?",
            "call_elapsed_ms": 5000
        },
        {
            "call_id": CALL_ID,
            "speaker": "customer",
            "text": "Yes, who is this?",
            "call_elapsed_ms": 8000,
            "sentiment": "neutral"
        },
        {
            "call_id": CALL_ID,
            "speaker": "agent",
            "text": "This is about your loan. Your EMI is overdue.",
            "call_elapsed_ms": 14000
        },
        {
            "call_id": CALL_ID,
            "speaker": "customer",
            "text": "I lost my job recently and cannot pay right now.",
            "call_elapsed_ms": 22000,
            "sentiment": "negative"
        },
        {
            "call_id": CALL_ID,
            "speaker": "agent",
            "text": "I understand. We have payment plans that can help.",
            "call_elapsed_ms": 30000
        },
        {
            "call_id": CALL_ID,
            "speaker": "customer",
            "text": "What kind of plans? Can I pay in parts?",
            "call_elapsed_ms": 38000,
            "sentiment": "positive"
        },
    ]

    for i, utterance in enumerate(utterances):
        response = requests.post(
            f"{BASE_URL}/api/v1/test/utterance",
            json=utterance
        )

        if response.status_code == 200:
            data = response.json()
            print(f"   [{i+1}] Added: {utterance['speaker']} - \"{utterance['text'][:50]}...\"")
        else:
            print(f"   ❌ Error adding utterance: {response.text}")

        time.sleep(0.5)  # Small delay between utterances

    print("   ✅ All utterances added\n")


def test_view_streams():
    """Test viewing streams."""
    print("4. Testing view streams...")
    time.sleep(2)  # Wait for processing

    response = requests.get(f"{BASE_URL}/api/v1/test/streams/{CALL_ID}")

    if response.status_code == 200:
        data = response.json()
        print(f"   Transcripts: {len(data['transcripts'])}")
        print(f"   Insights: {len(data['insights'])}")
        print(f"   Insight Jobs: {len(data['insight_jobs'])}")
        print("   ✅ Streams retrieved\n")
    else:
        print(f"   ❌ Error: {response.text}\n")


def test_trigger_insights():
    """Test manual insight generation."""
    print("5. Testing manual insight generation...")

    response = requests.post(
        f"{BASE_URL}/api/v1/insights/generate",
        json={"call_id": CALL_ID, "trigger": "agent_refresh"}
    )

    if response.status_code == 200:
        data = response.json()
        print(f"   Status: {data['status']}")
        print("   ✅ Insight generation triggered\n")
    else:
        print(f"   ❌ Error: {response.text}\n")


def main():
    """Run all tests."""
    print("=" * 60)
    print("AI Collections Assistant - Quick Test")
    print("=" * 60)
    print()

    try:
        test_health()
        test_get_context()
        test_add_utterances()
        test_view_streams()
        test_trigger_insights()

        print("=" * 60)
        print("✅ ALL TESTS PASSED!")
        print("=" * 60)
        print()
        print("Next steps:")
        print("1. Check Redis streams: redis-cli XREAD STREAMS call:test-call-001:transcript 0")
        print("2. Start workers to process insights")
        print("3. Test WebSocket connection with test_websocket.html")

    except requests.exceptions.ConnectionError:
        print("\n❌ ERROR: Cannot connect to server!")
        print("Make sure FastAPI server is running:")
        print("   cd backend")
        print("   python -m uvicorn app.main:app --reload")
    except AssertionError as e:
        print(f"\n❌ Test failed: {e}")
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")


if __name__ == "__main__":
    main()
