# 🚀 Quick Start Guide - AI Collections Assistant Backend

## Problem: WebSocket Error?

If you're seeing a WebSocket error in `test_websocket.html`, it means the **FastAPI server is not running**.

Follow these steps to get everything working:

---

## Step 1: Install Redis (Required)

### Option A: Windows Redis (Easiest)

1. **Download Memurai** (Redis for Windows):
   - Visit: https://www.memurai.com/get-memurai
   - Download and install Memurai (free version)
   - It will run automatically as a Windows service

2. **OR Download Redis directly**:
   - Visit: https://github.com/tporadowski/redis/releases
   - Download `Redis-x64-5.0.14.1.msi`
   - Install and start Redis service

### Option B: Docker (If you have Docker Desktop)

```bash
docker run -d -p 6379:6379 --name redis-collections redis:7
```

### Verify Redis is Running:

```bash
# Open Command Prompt and try:
redis-cli ping

# Should return: PONG
```

---

## Step 2: Install Python Dependencies

Open **Command Prompt** or **PowerShell** and run:

```bash
# Navigate to backend folder
cd "C:\Users\joshm\OneDrive\Documents\Ebix collections\backend"

# Create virtual environment (first time only)
python -m venv venv

# Activate virtual environment
venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

---

## Step 3: Configure Environment (Optional)

```bash
# Copy example environment file
copy .env.example .env

# Edit .env if you have Claude API key
# Otherwise, it will work with mock data
notepad .env
```

**Note**: Without a Claude API key, the system will return mock insights. The rest will work fine!

---

## Step 4: Start the FastAPI Server

In the **same terminal** (with venv activated):

```bash
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

You should see:

```
INFO:     Uvicorn running on http://0.0.0.0:8000 (Press CTRL+C to quit)
INFO:     Started reloader process [xxxxx]
INFO:     Started server process [xxxxx]
INFO:     Waiting for application startup.
Starting up AI Collections Assistant API...
Connected to Redis
INFO:     Application startup complete.
```

**Keep this terminal open!** The server needs to stay running.

---

## Step 5: Test the WebSocket

Now open `test_websocket.html` in your browser:

```
file:///C:/Users/joshm/OneDrive/Documents/Ebix%20collections/backend/test_websocket.html
```

1. Click **"🔌 Connect"**
2. You should see: **"✅ Connected successfully!"**
3. Click **"📝 Send Test Utterances"**
4. Watch the transcripts appear in real-time!

---

## Quick Test Without Workers

You can test the basic functionality without starting the workers:

```bash
# In a new terminal (with venv activated)
python quick_test.py
```

This will test the REST API endpoints.

---

## Full Test With Workers (Optional)

To test the **full AI insights generation**, start the workers:

### Terminal 1: FastAPI Server (already running)
```bash
python -m uvicorn app.main:app --reload
```

### Terminal 2: Transcript Worker
```bash
cd "C:\Users\joshm\OneDrive\Documents\Ebix collections\backend"
venv\Scripts\activate
python -m app.workers.transcript_worker
```

### Terminal 3: Insights Worker
```bash
cd "C:\Users\joshm\OneDrive\Documents\Ebix collections\backend"
venv\Scripts\activate
python -m app.workers.insights_worker
```

---

## Troubleshooting

### Error: "redis.exceptions.ConnectionError"

**Problem**: Redis is not running.

**Solution**:
- Make sure Redis/Memurai is installed and running
- Check services: `services.msc` → Look for Redis/Memurai
- Or start manually: `redis-server`

### Error: "ModuleNotFoundError: No module named 'fastapi'"

**Problem**: Virtual environment not activated or dependencies not installed.

**Solution**:
```bash
cd "C:\Users\joshm\OneDrive\Documents\Ebix collections\backend"
venv\Scripts\activate
pip install -r requirements.txt
```

### WebSocket Error: "WebSocket connection failed"

**Problem**: FastAPI server is not running.

**Solution**: Make sure you ran Step 4 above.

### Error: "Port 8000 already in use"

**Problem**: Another service is using port 8000.

**Solution**: Use a different port:
```bash
python -m uvicorn app.main:app --reload --port 8001
```

Then update the WebSocket URL in `test_websocket.html` to use port 8001.

---

## What Works Without Claude API Key?

✅ REST API endpoints
✅ WebSocket connection
✅ Transcript streaming
✅ Sentiment detection (basic)
✅ Topic detection
⚠️ **Mock insights** (not real AI, just placeholder)

## What Needs Claude API Key?

❌ Real AI-generated insights from Claude Sonnet 4

To get a Claude API key:
1. Visit: https://console.anthropic.com/
2. Sign up / Log in
3. Get API key from dashboard
4. Add to `.env`: `CLAUDE_API_KEY=sk-ant-...`

---

## Quick Commands Reference

```bash
# Check if Redis is running
redis-cli ping

# Check if FastAPI is running
curl http://localhost:8000/health

# View backend logs
# (Just look at the terminal where uvicorn is running)

# Stop everything
# Press CTRL+C in each terminal

# View Redis data
redis-cli
> KEYS call:*
> XREAD STREAMS call:test-ws-001:transcript 0
```

---

## Need Help?

- Check the terminal where `uvicorn` is running for error messages
- Make sure Redis is running: `redis-cli ping`
- Make sure port 8000 is not blocked by firewall
- Try accessing http://localhost:8000 in your browser (should show API info)

---

## Summary

**Minimum to test WebSocket**:
1. ✅ Install Redis/Memurai
2. ✅ Install Python dependencies (`pip install -r requirements.txt`)
3. ✅ Start FastAPI server (`python -m uvicorn app.main:app --reload`)
4. ✅ Open `test_websocket.html` and click Connect

That's it! The WebSocket will work without workers or Claude API.
