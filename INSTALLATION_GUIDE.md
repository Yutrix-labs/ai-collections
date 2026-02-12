# AI Collections Assistant - Installation & Testing Guide

Complete guide to set up and test the AI Collections Assistant backend from scratch.

---

## Table of Contents

1. [Prerequisites](#1-prerequisites)
2. [Clone the Repository](#2-clone-the-repository)
3. [Install Redis (Memurai)](#3-install-redis-memurai)
4. [Set Up Python Environment](#4-set-up-python-environment)
5. [Configure Environment Variables](#5-configure-environment-variables)
6. [Start the FastAPI Server](#6-start-the-fastapi-server)
7. [Run the Quick Test](#7-run-the-quick-test)
8. [Start the Insights Worker](#8-start-the-insights-worker)
9. [Test WebSocket in Browser](#9-test-websocket-in-browser)
10. [Verify AI Insights](#10-verify-ai-insights)
11. [API Reference](#11-api-reference)
12. [Troubleshooting](#12-troubleshooting)

---

## 1. Prerequisites

Ensure the following are installed on your Windows machine:

| Software   | Version  | Download                                      |
|------------|----------|-----------------------------------------------|
| Python     | 3.10+    | https://www.python.org/downloads/             |
| Git        | Latest   | https://git-scm.com/download/win              |
| Memurai    | 4.x      | https://www.memurai.com/get-memurai           |

**Verify installations** (open Command Prompt or PowerShell):

```bash
python --version        # Should show Python 3.10+
git --version           # Should show git version
```

---

## 2. Clone the Repository

```bash
# Choose a directory for the project
cd C:\Users\%USERNAME%\Documents

# Clone the repo
git clone https://github.com/Yutrix-labs/AI_Collections.git

# Navigate to the backend folder
cd AI_Collections
```

You should see these backend files:

```
AI_Collections/
├── app/                    # Backend application code
│   ├── api/                # REST and WebSocket endpoints
│   ├── services/           # Business logic (insights engine, gateway)
│   ├── models/             # Data models
│   ├── utils/              # Redis client, prompt builder
│   └── workers/            # Background workers
├── .env.example            # Environment variable template
├── requirements.txt        # Python dependencies
├── quick_test.py           # Automated test script
├── test_websocket.html     # Browser-based WebSocket test
├── start_server.bat        # One-click server starter
└── README.md               # Project overview
```

---

## 3. Install Redis (Memurai)

Memurai is a Redis-compatible server for Windows.

### Option A: MSI Installer (Recommended)

1. Download from https://www.memurai.com/get-memurai
2. Run the installer — accept defaults
3. Memurai will start automatically as a Windows service

### Option B: Docker (if Docker Desktop is installed)

```bash
docker run -d -p 6379:6379 --name redis-collections redis:7
```

### Verify Redis is running:

```bash
# Using Memurai CLI (if installed via MSI)
"C:\Program Files\Memurai\memurai-cli.exe" ping

# Should return: PONG
```

Or check Windows Services:
1. Press `Win + R`, type `services.msc`, press Enter
2. Look for **Memurai** — status should be **Running**

---

## 4. Set Up Python Environment

Open **Command Prompt** or **PowerShell** and run:

```bash
# Navigate to the project root
cd C:\Users\%USERNAME%\Documents\AI_Collections

# Create a virtual environment
python -m venv venv

# Activate the virtual environment
venv\Scripts\activate

# You should see (venv) in your prompt:
# (venv) C:\Users\...\AI_Collections>

# Install dependencies
pip install -r requirements.txt

# Also install requests (needed for quick_test.py)
pip install requests
```

**Expected output**: All packages install successfully (fastapi, uvicorn, redis, anthropic, pydantic, etc.)

---

## 5. Configure Environment Variables

```bash
# Copy the example environment file
copy .env.example .env

# Open .env in a text editor
notepad .env
```

Edit the `.env` file with your settings:

```env
# Redis Configuration (default works if Memurai is running locally)
REDIS_URL=redis://localhost:6379/0

# Claude API Key (get from https://console.anthropic.com/)
CLAUDE_API_KEY=sk-ant-api03-YOUR-KEY-HERE

# CORS Settings (must be valid JSON array)
ALLOWED_ORIGINS=["http://localhost:3000","http://localhost:8000"]
```

**Important notes:**
- `CLAUDE_API_KEY`: Required for real AI insights. Without it, you get mock/placeholder insights.
- `ALLOWED_ORIGINS`: Must be a JSON array (with square brackets and quotes), not comma-separated.
- All other defaults are fine for development.

---

## 6. Start the FastAPI Server

### Option A: Manual start (recommended for first time)

```bash
# Make sure venv is activated
venv\Scripts\activate

# Start the server
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### Option B: Use the batch file

```bash
start_server.bat
```

**Expected output:**

```
INFO:     Uvicorn running on http://0.0.0.0:8000 (Press CTRL+C to quit)
INFO:     Started reloader process [xxxxx] using WatchFiles
INFO:     Started server process [xxxxx]
INFO:     Waiting for application startup.
Starting up AI Collections Assistant API...
Connected to Redis
INFO:     Application startup complete.
```

**Keep this terminal open!** The server must stay running.

### Verify the server is running:

Open a browser and go to: http://localhost:8000

You should see:

```json
{"name": "AI Collections Assistant API", "version": "1.0.0", ...}
```

---

## 7. Run the Quick Test

Open a **new terminal** (keep the server running in the first one):

```bash
# Navigate to project
cd C:\Users\%USERNAME%\Documents\AI_Collections

# Activate venv
venv\Scripts\activate

# Run the test (set encoding for emoji support)
set PYTHONIOENCODING=utf-8
python quick_test.py
```

**Expected output:**

```
============================================================
AI Collections Assistant - Quick Test
============================================================

1. Testing health endpoint...
   Status: 200
   Response: {'status': 'healthy'}
   ✅ Health check passed

2. Testing GET call context...
   Status: 200
   Customer: Rajesh Kumar Sharma
   DPD: 67 days
   Initial insights: 3
   ✅ Context retrieved

3. Testing add utterances...
   [1] Added: agent - "Good morning, am I speaking with Mr. Rajesh?..."
   [2] Added: customer - "Yes, who is this?..."
   [3] Added: agent - "This is about your loan. Your EMI is overdue...."
   [4] Added: customer - "I lost my job recently and cannot pay right now...."
   [5] Added: agent - "I understand. We have payment plans that can help...."
   [6] Added: customer - "What kind of plans? Can I pay in parts?..."
   ✅ All utterances added

4. Testing view streams...
   Transcripts: 6
   Insights: 0
   Insight Jobs: 0
   ✅ Streams retrieved

5. Testing manual insight generation...
   Status: queued
   ✅ Insight generation triggered

============================================================
✅ ALL TESTS PASSED!
============================================================
```

**What this tests:**
- Health check endpoint
- Customer context retrieval (mock data for Rajesh Kumar Sharma)
- Adding transcript utterances to Redis streams
- Reading streams back
- Queuing an insight generation job

---

## 8. Start the Insights Worker

The insights worker is a separate process that picks up insight generation jobs from Redis and calls the Claude API.

Open a **third terminal**:

```bash
# Navigate to project
cd C:\Users\%USERNAME%\Documents\AI_Collections

# Activate venv
venv\Scripts\activate

# Start the worker
set PYTHONIOENCODING=utf-8
python -m app.workers.insights_worker
```

**Expected output:**

```
Starting insights worker...
Connected to Redis
Generating insights for call test-call-001, trigger: agent_refresh
Generated 4 insights for call test-call-001
```

If you see "Generated X insights", the Claude API integration is working.

**Keep this terminal open!** The worker runs continuously.

### Verify insights were generated:

In your second terminal (with venv activated):

```bash
python -c "import requests, json; r = requests.get('http://localhost:8000/api/v1/test/streams/test-call-001'); [print(f'[{i[\"data\"].get(\"type\",\"?\")}] {i[\"data\"].get(\"text\",\"?\")}') for i in r.json().get('insights',[])]"
```

You should see insights like:

```
[alert] Customer approaching 90 DPD threshold (currently 67 days)...
[policy] 50% penalty waiver available if ₹50,000+ committed...
[intent] Recent ₹5,000 payment shows willingness despite bounces...
[suggestion] Propose structured catch-up plan: ₹25,000 now + ₹25,000 in 15 days...
```

---

## 9. Test WebSocket in Browser

1. Open `test_websocket.html` in your browser:
   - Double-click the file, OR
   - Navigate to: `file:///C:/Users/%USERNAME%/Documents/AI_Collections/test_websocket.html`

2. Click **"Connect"**
   - Status should turn green: "Connected to call test-ws-001"

3. Click **"Send Test Utterances"**
   - You should see yellow transcript messages appear in real-time:
     ```
     🎤 TRANSCRIPT — speaker: "agent", text: "Good morning, this is about your loan"
     🎤 TRANSCRIPT — speaker: "customer", text: "I lost my job and cannot pay"
     ...
     ```

4. Click **"Refresh Insights"**
   - After a few seconds, green insight messages appear:
     ```
     💡 INSIGHT — type: "alert", text: "Customer approaching 90 DPD threshold..."
     💡 INSIGHT — type: "suggestion", text: "Propose structured catch-up plan..."
     ```

**What this tests:**
- WebSocket connection between browser and FastAPI
- Real-time transcript streaming via Redis Streams
- Customer profile auto-loading on WebSocket connect
- AI insight generation triggered by the browser
- Real-time insight delivery back to the browser

---

## 10. Verify AI Insights

### With Claude API Key (real insights):

If your `.env` has a valid `CLAUDE_API_KEY`, insights are generated by Claude Sonnet and are contextual to the customer profile:

| Type       | Priority | Example                                                            |
|------------|----------|--------------------------------------------------------------------|
| alert      | high     | Customer approaching 90 DPD threshold (currently 67 days)          |
| policy     | high     | 50% penalty waiver available if ₹50,000+ committed within 30 days |
| intent     | medium   | Recent ₹5,000 payment shows willingness despite bounces            |
| suggestion | medium   | Propose structured catch-up plan: ₹25,000 now + ₹25,000 in 15 days|

### Without Claude API Key (mock insights):

Without an API key, the system returns a single mock insight:

```json
{
  "type": "suggestion",
  "text": "Consider offering a restructured payment plan",
  "priority": "high"
}
```

### Check Redis directly:

```bash
"C:\Program Files\Memurai\memurai-cli.exe" XREAD STREAMS call:test-ws-001:insights 0
```

---

## 11. API Reference

### REST Endpoints

| Method | Endpoint                              | Description                        |
|--------|---------------------------------------|------------------------------------|
| GET    | `/`                                   | API info                           |
| GET    | `/health`                             | Health check                       |
| GET    | `/api/v1/health`                      | Health check (prefixed)            |
| GET    | `/api/v1/calls/{call_id}/context`     | Get customer context for a call    |
| POST   | `/api/v1/insights/generate`           | Trigger insight generation         |
| POST   | `/api/v1/calls/{call_id}/agent-action`| Agent actions (dismiss/accept)     |
| POST   | `/api/v1/test/utterance`              | Add test utterance (dev only)      |
| GET    | `/api/v1/test/streams/{call_id}`      | View all streams for a call (dev)  |

### WebSocket Endpoint

```
ws://localhost:8000/api/v1/calls/{call_id}/stream?token={jwt_token}
```

**Server -> Client events:**
- `transcript` — New utterance from the call
- `insight` — New AI-generated insight
- `sentiment_update` — Sentiment change detected
- `disposition_prefill` — Auto-fill form data
- `call_status` — Call state change

**Client -> Server actions:**
- `{"action": "refresh_insights"}` — Request new insights
- `{"action": "dismiss_insight", "insight_id": "..."}` — Dismiss an insight
- `{"action": "accept_suggestion", "insight_id": "..."}` — Accept a suggestion
- `{"action": "resync", "last_utterance_id": "0", "last_insight_id": "0"}` — Resync after reconnect

---

## 12. Troubleshooting

### "redis.exceptions.ConnectionError"

**Cause:** Redis/Memurai is not running.

**Fix:**
- Check Windows Services (`services.msc`) — look for **Memurai**, ensure it's Running
- Or start manually: `"C:\Program Files\Memurai\memurai.exe"`

### "ModuleNotFoundError: No module named 'fastapi'"

**Cause:** Virtual environment not activated or dependencies not installed.

**Fix:**
```bash
cd C:\Users\%USERNAME%\Documents\AI_Collections
venv\Scripts\activate
pip install -r requirements.txt
```

### "error parsing value for field 'allowed_origins'"

**Cause:** `ALLOWED_ORIGINS` in `.env` is not valid JSON.

**Fix:** Use JSON array format:
```env
ALLOWED_ORIGINS=["http://localhost:3000","http://localhost:8000"]
```

### WebSocket says "WebSocket connection failed"

**Cause:** FastAPI server is not running.

**Fix:** Start the server (see Step 6).

### "Port 8000 already in use"

**Cause:** Another process is using port 8000.

**Fix:** Use a different port:
```bash
python -m uvicorn app.main:app --reload --port 8001
```
Then update the URL in `test_websocket.html` line 102:
```js
const BASE_URL = 'http://localhost:8001';
```
And line 112:
```js
ws = new WebSocket(`ws://localhost:8001/api/v1/calls/${callId}/stream?token=demo-token`);
```

### Insights show "No customer profile loaded"

**Cause:** Customer profile was not cached before insight generation.

**Fix:** This is now automatic — the WebSocket endpoint caches the profile on connect. If testing via REST, call the context endpoint first:
```bash
curl http://localhost:8000/api/v1/calls/test-call-001/context
```

### UnicodeEncodeError with emojis in quick_test.py

**Cause:** Windows console doesn't support UTF-8 by default.

**Fix:**
```bash
set PYTHONIOENCODING=utf-8
python quick_test.py
```

### Insights worker shows "Generated 0 insights"

**Cause:** Rate limiting — the same insight type was generated recently.

**Fix:** Wait for the rate limit to expire (default: 30-60 seconds) or clear Redis:
```bash
"C:\Program Files\Memurai\memurai-cli.exe" FLUSHDB
```

---

## Terminal Summary

When fully running, you should have **3 terminals** open:

| Terminal | Command                                                    | Purpose             |
|----------|------------------------------------------------------------|---------------------|
| 1        | `python -m uvicorn app.main:app --reload --port 8000`     | FastAPI server      |
| 2        | `python -m app.workers.insights_worker`                    | AI insights worker  |
| 3        | Available for running `quick_test.py` or other commands    | Testing             |

Plus `test_websocket.html` open in a browser for WebSocket testing.

---

## Architecture Overview

```
Browser (test_websocket.html)
    │
    ├── HTTP POST /api/v1/test/utterance ──→ FastAPI ──→ Redis Stream (transcript)
    │                                                          │
    ├── WebSocket ←──────────────────────── FastAPI ←──── Redis Stream (listens)
    │       │                                                  │
    │       └── {"action":"refresh_insights"} ──→ Redis Stream (insight_jobs)
    │                                                          │
    │                                          Insights Worker ←┘
    │                                               │
    │                                          Claude API (Sonnet)
    │                                               │
    │                                          Redis Stream (insights)
    │                                               │
    └── 💡 INSIGHT event ←──────────────── FastAPI WebSocket (listens)
```

---

*Last updated: February 2026*
