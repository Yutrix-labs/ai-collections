# Testing the AI Collections Assistant Backend

## Quick Start Test

### 1. Start Redis

```bash
# Using Docker (recommended)
docker run -d -p 6379:6379 --name redis-collections redis:7

# OR using Windows Redis
# Download from: https://github.com/microsoftarchive/redis/releases
redis-server
```

### 2. Start the FastAPI Server

```bash
cd "C:\Users\joshm\OneDrive\Documents\Ebix collections\backend"

# Create virtual environment (first time only)
python -m venv venv
venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Start server
python -m uvicorn app.main:app --reload --port 8000
```

Server will start at: **http://localhost:8000**

### 3. Test the REST API

Open your browser or use curl:

**Health Check**:
```bash
curl http://localhost:8000/health
```

**Get Call Context**:
```bash
curl http://localhost:8000/api/v1/calls/demo-123/context
```

You should see customer profile, loan details, payment history, and initial insights!

---

## Test with Simple HTML Client

Create a test file to try the WebSocket connection:

### test_websocket.html

```html
<!DOCTYPE html>
<html>
<head>
    <title>WebSocket Test</title>
</head>
<body>
    <h1>AI Collections Assistant - WebSocket Test</h1>

    <div>
        <button onclick="connect()">Connect</button>
        <button onclick="disconnect()">Disconnect</button>
        <button onclick="sendUtterance()">Send Test Utterance</button>
    </div>

    <div>
        <h3>Status: <span id="status">Disconnected</span></h3>
        <h3>Messages:</h3>
        <div id="messages" style="border: 1px solid #ccc; padding: 10px; height: 400px; overflow-y: auto;"></div>
    </div>

    <script>
        let ws = null;
        const callId = 'demo-call-123';

        function connect() {
            ws = new WebSocket(`ws://localhost:8000/api/v1/calls/${callId}/stream?token=demo-token`);

            ws.onopen = () => {
                document.getElementById('status').textContent = 'Connected';
                addMessage('✅ Connected to WebSocket');
            };

            ws.onmessage = (event) => {
                const data = JSON.parse(event.data);
                addMessage(`📩 ${data.event}: ${JSON.stringify(data.payload, null, 2)}`);
            };

            ws.onerror = (error) => {
                addMessage('❌ Error: ' + error);
            };

            ws.onclose = () => {
                document.getElementById('status').textContent = 'Disconnected';
                addMessage('🔌 Disconnected');
            };
        }

        function disconnect() {
            if (ws) {
                ws.close();
            }
        }

        function sendUtterance() {
            // Simulate adding an utterance to Redis
            fetch('http://localhost:8000/api/v1/test/utterance', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({
                    call_id: callId,
                    speaker: 'customer',
                    text: 'I need help with my payment',
                    call_elapsed_ms: 5000
                })
            }).then(() => addMessage('📝 Sent test utterance'));
        }

        function addMessage(msg) {
            const div = document.getElementById('messages');
            div.innerHTML += `<div style="margin-bottom: 10px; padding: 5px; background: #f0f0f0;">${msg}</div>`;
            div.scrollTop = div.scrollHeight;
        }
    </script>
</body>
</html>
```

Save this and open in browser!

---

## Test Using Redis CLI

### Simulate a Live Call

**1. Add utterances to transcript stream:**

```bash
# Customer utterance 1
redis-cli XADD call:demo-123:transcript * speaker customer text "I lost my job and cannot pay" call_elapsed_ms 5000 sentiment negative

# Agent response
redis-cli XADD call:demo-123:transcript * speaker agent text "I understand sir. We have options to help you" call_elapsed_ms 8000 sentiment neutral

# Customer utterance 2
redis-cli XADD call:demo-123:transcript * speaker customer text "What kind of options?" call_elapsed_ms 12000 sentiment positive

# Customer utterance 3 (triggers LLM after 3 utterances)
redis-cli XADD call:demo-123:transcript * speaker customer text "Can I pay in parts?" call_elapsed_ms 18000 sentiment positive
```

**2. Check if insights were generated:**

```bash
# View insights stream
redis-cli XREAD STREAMS call:demo-123:insights 0

# View insight jobs queue
redis-cli XREAD STREAMS call:demo-123:insight_jobs 0
```

---

## Test with Python Script

Create `test_api.py`:

```python
import asyncio
import aiohttp
import json

async def test_rest_api():
    """Test REST endpoints"""
    async with aiohttp.ClientSession() as session:

        # 1. Get call context
        print("1. Testing GET /calls/{call_id}/context...")
        async with session.get('http://localhost:8000/api/v1/calls/demo-123/context') as resp:
            context = await resp.json()
            print(f"✅ Customer: {context['customer']['name']}")
            print(f"✅ DPD: {context['additional']['dpd']} days")
            print(f"✅ Initial insights: {len(context['initial_insights'])}")

        # 2. Trigger insight generation
        print("\n2. Testing POST /insights/generate...")
        async with session.post(
            'http://localhost:8000/api/v1/insights/generate',
            json={'call_id': 'demo-123', 'trigger': 'agent_refresh'}
        ) as resp:
            result = await resp.json()
            print(f"✅ Status: {result['status']}")

async def test_websocket():
    """Test WebSocket connection"""
    async with aiohttp.ClientSession() as session:
        print("\n3. Testing WebSocket connection...")

        async with session.ws_connect(
            'http://localhost:8000/api/v1/calls/demo-123/stream?token=demo-token'
        ) as ws:
            print("✅ Connected to WebSocket")

            # Send refresh request
            await ws.send_json({'action': 'refresh_insights'})
            print("📤 Sent refresh_insights")

            # Listen for 5 seconds
            try:
                async with asyncio.timeout(5):
                    async for msg in ws:
                        if msg.type == aiohttp.WSMsgType.TEXT:
                            data = json.loads(msg.data)
                            print(f"📩 Received: {data['event']}")
                        elif msg.type == aiohttp.WSMsgType.ERROR:
                            break
            except asyncio.TimeoutError:
                print("⏱️ Timeout (normal for testing)")

            print("✅ WebSocket test complete")

async def main():
    print("=== Testing AI Collections Assistant Backend ===\n")
    await test_rest_api()
    await test_websocket()
    print("\n=== All tests complete ===")

if __name__ == '__main__':
    asyncio.run(main())
```

Run it:
```bash
python test_api.py
```

---

## Test with Postman

### 1. GET Call Context
- URL: `http://localhost:8000/api/v1/calls/demo-123/context`
- Method: GET
- Expected: 200 OK with customer profile

### 2. POST Generate Insights
- URL: `http://localhost:8000/api/v1/insights/generate`
- Method: POST
- Headers: `Content-Type: application/json`
- Body:
```json
{
    "call_id": "demo-123",
    "trigger": "agent_refresh"
}
```

### 3. WebSocket Connection
- URL: `ws://localhost:8000/api/v1/calls/demo-123/stream?token=demo-token`
- Protocol: WebSocket
- Send message:
```json
{
    "action": "refresh_insights"
}
```

---

## Start Background Workers (for full test)

In separate terminals:

**Terminal 1 - Transcript Worker:**
```bash
cd "C:\Users\joshm\OneDrive\Documents\Ebix collections\backend"
venv\Scripts\activate
python -m app.workers.transcript_worker
```

**Terminal 2 - Insights Worker:**
```bash
cd "C:\Users\joshm\OneDrive\Documents\Ebix collections\backend"
venv\Scripts\activate
python -m app.workers.insights_worker
```

Now when you add utterances to Redis, the workers will:
1. Process sentiment
2. Detect topics
3. Generate insights via Claude
4. Push to WebSocket clients

---

## Quick Integration Test

**Full flow test:**

1. Start Redis
2. Start FastAPI server
3. Start both workers
4. Open `test_websocket.html` in browser
5. Click "Connect"
6. Run Redis commands to add utterances
7. Watch insights appear in real-time!

---

## Expected Output

When working correctly, you should see:

```
📩 transcript: {"utterance_id": "...", "speaker": "customer", "text": "I need help"}
📩 insight: {"type": "intent", "text": "Customer seeking payment assistance", "priority": "high"}
📩 sentiment_update: {"overall": "negative", "trend": "declining"}
```

---

## Troubleshooting

**Redis connection error:**
```bash
# Check if Redis is running
redis-cli ping
# Should return: PONG
```

**ModuleNotFoundError:**
```bash
# Make sure virtual environment is activated
venv\Scripts\activate
pip install -r requirements.txt
```

**WebSocket not connecting:**
- Check FastAPI is running on port 8000
- Check browser console for errors
- Try `ws://localhost:8000` not `wss://` (no SSL)

**No insights generated:**
- Check if insights worker is running
- Check CLAUDE_API_KEY in .env file
- Check Redis streams: `redis-cli XREAD STREAMS call:demo-123:insight_jobs 0`
