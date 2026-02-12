# AI Collections Assistant - Backend

Real-time AI-powered insights engine for collections call agents.

## Architecture

```
┌──────────────────┐  ┌───────────────────┐  ┌──────────────┐
│ WebSocket        │  │ Transcript        │  │ AI Insights  │
│ Gateway          │← │ Aggregator        │← │ Engine       │
│ (FastAPI)        │  │ (sentiment+topic) │  │ (Claude 4)   │
└──────────────────┘  └───────────────────┘  └──────────────┘
         ↑                     ↑                      ↑
┌────────────────────────────────────────────────────────────┐
│              Redis Streams + Cache Layer                  │
│  call:{id}:transcript • call:{id}:insights • sentiment    │
└────────────────────────────────────────────────────────────┘
```

## Setup

### Prerequisites

- Python 3.10+
- Redis 7.0+
- Claude API key (from Anthropic)

### Installation

1. **Create virtual environment**:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

2. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

3. **Configure environment**:
   ```bash
   cp .env.example .env
   # Edit .env with your configuration
   ```

4. **Start Redis**:
   ```bash
   docker run -d -p 6379:6379 redis:7
   ```

## Running the Services

### 1. Start FastAPI Server

```bash
cd backend
uvicorn app.main:app --reload --port 8000
```

API will be available at: `http://localhost:8000`

### 2. Start Background Workers

In separate terminals:

```bash
# Transcript Worker
python -m app.workers.transcript_worker

# Insights Worker
python -m app.workers.insights_worker
```

## API Endpoints

### REST API

- `GET /api/v1/calls/{call_id}/context` - Get call context
- `POST /api/v1/insights/generate` - Trigger insight generation
- `POST /api/v1/calls/{call_id}/agent-action` - Agent actions
- `GET /health` - Health check

### WebSocket

- `ws://localhost:8000/api/v1/calls/{call_id}/stream?token={jwt}` - Real-time streaming

#### Server → Client Events:
- `transcript` - New utterance
- `insight` - New AI insight
- `sentiment_update` - Sentiment change
- `data_surface` - Dynamic data
- `disposition_prefill` - Form auto-fill
- `call_status` - Call state change

#### Client → Server Events:
- `refresh_insights` - Manual insight refresh
- `dismiss_insight` - Dismiss insight card
- `accept_suggestion` - Accept suggestion
- `resync` - Reconnection resync

## Development

### Project Structure

```
backend/
├── app/
│   ├── main.py                 # FastAPI application
│   ├── config.py               # Settings
│   ├── models/                 # Data models
│   │   ├── call.py
│   │   └── websocket.py
│   ├── services/               # Business logic
│   │   ├── websocket_gateway.py
│   │   ├── transcript_aggregator.py
│   │   └── ai_insights_engine.py
│   ├── api/                    # API endpoints
│   │   ├── rest.py
│   │   └── websocket.py
│   ├── utils/                  # Utilities
│   │   ├── redis_client.py
│   │   └── prompt_builder.py
│   └── workers/                # Background workers
│       ├── transcript_worker.py
│       └── insights_worker.py
└── requirements.txt
```

### Testing

Simulate a call by publishing to Redis:

```bash
# Add transcript utterance
redis-cli XADD call:demo-123:transcript * \
  speaker customer \
  text "I need help with my payment" \
  call_elapsed_ms 5000 \
  sentiment neutral

# Check insights stream
redis-cli XREAD STREAMS call:demo-123:insights 0
```

## Configuration

Key environment variables:

- `REDIS_URL` - Redis connection string
- `CLAUDE_API_KEY` - Anthropic API key
- `LLM_MODEL` - Claude model (default: claude-sonnet-4-5-20250929)
- `LLM_TEMPERATURE` - Temperature (default: 0.3)
- `RATE_LIMIT_*` - Rate limiting (seconds)

See `.env.example` for full configuration.

## Features

- ✅ Real-time WebSocket streaming
- ✅ AI insights generation (Claude Sonnet 4)
- ✅ Sentiment tracking and trend detection
- ✅ Topic detection (payment, legal, hardship, etc.)
- ✅ Rate limiting per insight type
- ✅ Reconnection with resync
- ✅ Redis Streams architecture
- ✅ Async/await throughout

## License

Proprietary - Ebix Collections
