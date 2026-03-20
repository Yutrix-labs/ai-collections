# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

AI Collections Assistant — a real-time AI-powered call assistant for bank collections agents. The system handles live telephony calls via Exotel Click2Call, transcribes audio in real-time using LiveKit + Deepgram, and streams transcripts and AI insights to a Next.js frontend via WebSockets.

## Repository Structure

This is a monorepo with two branches that have diverged:

- **`main` branch**: Contains the original Python FastAPI prototype backend (in `app/`). This is a separate codebase from the active development branch and uses Redis Streams, Claude AI, and raw WebSockets.
- **`v1.0.0.0` branch** (active development): Contains the production monorepo with `frontend/` and `backend/` directories. All new work should happen here.

### v1.0.0.0 Branch Layout

```
frontend/                    # Next.js 16 app (TypeScript, React 19.2)
backend/
  src/main/java/labs/yutrix/uw/   # Spring Boot 4 (Java 17, Maven)
  listening-agent/                 # Python LiveKit agent (Deepgram STT)
```

## Commands

### Frontend (`frontend/`)
```bash
npm run dev          # Start dev server (Turbopack)
npm run build        # Production build
npm run start        # Start production server
npm run lint         # ESLint
```

### Backend (`backend/`)
```bash
./mvnw spring-boot:run              # Run Spring Boot (port 8080, context-path /collassistantapi)
./mvnw spring-boot:run -Dspring-boot.run.profiles=dev   # Run with dev profile (debug logging)
./mvnw test                          # Run tests
./mvnw clean package                 # Build JAR
```

### Listening Agent (`backend/listening-agent/`)
```bash
uv sync                              # Install dependencies
uv run listening-agent               # Start the LiveKit transcriber agent
```

## Architecture

### Data Flow

```
Exotel Click2Call (telephony)
    │
    ▼
LiveKit Room (audio routing)
    │
    ▼
Listening Agent (Python) ──── Deepgram Nova-3 STT
    │                          (dual-speaker: SIP 16kHz, agent native)
    │
    ├── POST /collassistantapi/transcript/push   (transcript turns)
    ├── POST /collassistantapi/call/meet-url     (LiveKit Meet URL for agent)
    │
    ▼
Spring Boot Backend (Java) ──── In-memory SessionStore
    │                            (triple-key: sessionId, mobile, callSid)
    │
    ├── STOMP WebSocket /ws      (real-time to frontend)
    │   ├── /topic/call/{sessionId}/transcript
    │   └── /topic/call/{sessionId}/meet-url
    │
    ▼
Next.js Frontend
    ├── useStompClient hook      (STOMP over WebSocket)
    ├── LiveKit Meet iframe      (agent audio bridge)
    └── Axios REST client        (call start/end, customer data)
```

### Backend (Spring Boot 4)

- **Package**: `labs.yutrix.uw`
- **Base URL**: `http://localhost:8080/collassistantapi`
- **DB**: JPA auto-config disabled (all state is in-memory via `SessionStore`)
- **WebSocket**: STOMP over SockJS at `/ws`, broker prefix `/topic`, app prefix `/app`
- **API response wrapper**: `ApiResponse<T>` — all REST endpoints return `{success, message, data}`
- **Session management**: `SessionStore` uses `ConcurrentHashMap` with triple-key lookup (sessionId, customerMobile, exotelCallSid)
- **Telephony**: `ExotelService` initiates Click2Call, returns Exotel Call SID
- **AI**: Spring AI configured (OpenAI + Vertex AI Gemini) but currently disabled

Key modules:
- `call/` — CallController, ExotelService, SessionStore, CallSession
- `transcript/` — TranscriptController, TranscriptService (stores + broadcasts via STOMP)
- `customer/` — CustomerController (customer data lookup)
- `common/` — ApiResponse, GlobalExceptionHandler, EntityNotFoundException
- `config/` — CorsConfig, WebSocketConfig

### Listening Agent (Python)

- LiveKit Agents SDK v1.2 with Deepgram Nova-3 (multi-language)
- Silero VAD for voice activity detection
- Separate STT configs: SIP audio at 100ms endpointing (telephony latency), agent audio at 25ms
- Extracts Exotel Call SID from SIP participant attributes (`sip.h.x-exotel-callsid`)
- Posts transcript turns and LiveKit Meet URL to Spring Boot backend via HTTP
- Publishes silent audio track to keep SIP call alive

### Frontend (Next.js 16)

- **Path alias**: `@/*` maps to `./src/*`
- **i18n**: next-intl v4 with locale routing (`en`, `hi`, `mr`). All pages under `src/app/[locale]/`
- **Routing**: Uses Next.js 16 `proxy.ts` convention (not deprecated `middleware.ts`)
- **Real-time**: `useStompClient` hook for STOMP WebSocket connection to Spring Boot
- **REST**: Axios client in `src/lib/api/collections-api.ts` hitting `/collassistantapi/*` endpoints
- **LiveKit**: `@livekit/components-react` for agent audio bridge (iframe-based Meet URL)
- **Styling**: Tailwind CSS 4 + shadcn/ui (Radix UI). Use `npx shadcn@canary` for Tailwind v4 compat
- **Animations**: Framer Motion 12 for all component animations (no CSS `animation` in JSX)
- **Theme tokens**: Centralized in `src/config/theme.ts` and used via arbitrary Tailwind values when needed
- **Icons**: Lucide React exclusively
- **Mock data**: `src/data/mock-data.ts` with types from `src/types/collections.types.ts`

## Environment Variables

### Frontend (`frontend/.env.local`)
```
NEXT_PUBLIC_API_URL=http://localhost:8080/collassistantapi
```

### Backend (`backend/src/main/resources/application.yml`)
Key configs: `exotel.*`, `livekit.*`, `app.cors.allowed-origins`, `server.port` (8080)

### Listening Agent (`backend/listening-agent/.env`)
```
LIVEKIT_URL=wss://...
LIVEKIT_API_KEY=...
LIVEKIT_API_SECRET=...
BACKEND_URL=http://localhost:8080
```

## Conventions

- All REST responses use `ApiResponse<T>` wrapper (`{success, message, data}`)
- Frontend connects to backend at `/collassistantapi` context path
- Session lookup chain: frontend uses `sessionId`, listening agent uses `exotelCallSid`, both resolve to same `CallSession`
- Use Lombok (`@Data`, `@RequiredArgsConstructor`, `@Builder`, `@Slf4j`) for Java boilerplate
- Frontend i18n: all UI text in `messages/{locale}.json`, use `useTranslations()` hook
- Use Framer Motion for animations, Lucide React for icons, shadcn/ui for interactive components
- Use Tailwind CSS classes for all styling (avoid inline styles except for dynamic values)
