"""Demo runner — drives a scripted call through the REAL copilot, without telephony.

Why this exists
---------------
The Arabic (Kuwait) demo plays a pre-recorded customer clip in the browser instead of
placing a real call, so there is no audio reaching LiveKit and therefore no STT and no
transcript. Everything downstream of the transcript — insights, next-best-action,
contextual details — is driven purely by text via ``copilot.process_utterance()``, so we
can reproduce a completely genuine call by feeding it the English lines on cue.

This is deliberately NOT a fake-insights service: it runs the same CollectionsCopilot the
live agent runs, hits the same LLM, and pushes to the same backend endpoints. Only the
source of the words differs.

Flow per turn (identical to silent_transcriber_agent's transcribe_* handlers):

    POST /demo/utterance  ->  push_transcript(...)  +  copilot.process_utterance(...)

Endpoints
---------
POST /demo/start     {callSid, mobileNumber}            create + initialize the copilot
POST /demo/utterance {callSid, speaker, text, ...}      one transcript turn
POST /demo/end       {callSid}                          tear the copilot down
GET  /healthz
"""

import asyncio
import datetime
import logging
import os

import aiohttp
from aiohttp import web
from dotenv import load_dotenv

# Same as silent_transcriber_agent / ws_telephony_bridge: load .env in-process so the
# service runs identically whether started by hand or by the container command.
load_dotenv(".env")

from copilot.factory import create_copilot  # noqa: E402  (must follow load_dotenv)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [demo-runner] %(message)s",
)
logger = logging.getLogger("demo_runner")

BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8080")
HOST = os.getenv("DEMO_RUNNER_HOST", "0.0.0.0")
PORT = int(os.getenv("DEMO_RUNNER_PORT", "8092"))

# call_sid -> {"copilot": BaseCopilot, "mobile": str}
_SESSIONS: dict[str, dict] = {}
_LOCK = asyncio.Lock()
_http_session: aiohttp.ClientSession | None = None


async def get_http_session() -> aiohttp.ClientSession:
    """One shared session, carrying the backend API key like the live agent does."""
    global _http_session
    if _http_session is None or _http_session.closed:
        headers = {}
        api_key = os.getenv("BACKEND_API_KEY", "").strip()
        if api_key:
            headers["X-API-KEY"] = api_key
        _http_session = aiohttp.ClientSession(
            headers=headers,
            timeout=aiohttp.ClientTimeout(total=30),
        )
    return _http_session


async def push_transcript(call_sid: str, speaker: str, text: str,
                          timestamp: str, mobile_number: str | None = None) -> None:
    """POST a transcript turn to the backend — same contract as the live agent."""
    try:
        session = await get_http_session()
        payload = {
            "callSid": call_sid,
            "speaker": speaker,
            "text": text,
            "timestamp": timestamp,
        }
        if mobile_number:
            payload["mobileNumber"] = mobile_number

        async with session.post(
            f"{BACKEND_URL}/collassistantapi/transcript/push", json=payload
        ) as resp:
            if resp.status != 200:
                logger.warning("Transcript push returned %s: %s", resp.status, await resp.text())
    except Exception as e:
        logger.error("Failed to push transcript: %s", e)


async def _get_or_create(call_sid: str, mobile: str | None):
    """Fetch the copilot for this call, creating and initializing it on first use."""
    async with _LOCK:
        entry = _SESSIONS.get(call_sid)
        if entry:
            return entry["copilot"]

        http_session = await get_http_session()
        copilot = create_copilot(call_sid, http_session, mobile)
        await copilot.initialize()
        _SESSIONS[call_sid] = {"copilot": copilot, "mobile": mobile}
        logger.info("Copilot initialized | callSid=%s mobile=%s", call_sid, mobile)
        return copilot


async def handle_start(request: web.Request) -> web.Response:
    body = await request.json()
    call_sid = (body.get("callSid") or "").strip()
    mobile = (body.get("mobileNumber") or "").strip() or None
    if not call_sid:
        return web.json_response({"error": "callSid is required"}, status=400)

    await _get_or_create(call_sid, mobile)
    return web.json_response({"ok": True, "callSid": call_sid})


async def handle_utterance(request: web.Request) -> web.Response:
    body = await request.json()
    call_sid = (body.get("callSid") or "").strip()
    speaker = (body.get("speaker") or "").strip()
    text = (body.get("text") or "").strip()
    mobile = (body.get("mobileNumber") or "").strip() or None
    timestamp = (body.get("timestamp") or "").strip() or \
        datetime.datetime.now().strftime("%H:%M:%S")

    if not call_sid or not speaker or not text:
        return web.json_response(
            {"error": "callSid, speaker and text are required"}, status=400
        )
    if speaker not in ("agent", "customer"):
        return web.json_response(
            {"error": "speaker must be 'agent' or 'customer'"}, status=400
        )

    copilot = await _get_or_create(call_sid, mobile)
    logger.info("[%s] %s: %s", timestamp, speaker, text)

    # Same order the live agent uses: transcript first so the UI paints immediately,
    # then the copilot, whose LLM round-trip is much slower.
    await push_transcript(call_sid, speaker, text, timestamp, mobile)
    try:
        await copilot.process_utterance(speaker, text, timestamp)
    except Exception as e:
        # A copilot failure must never stop the demo — the transcript is already out.
        logger.error("Copilot failed on utterance | callSid=%s error=%s", call_sid, e)

    return web.json_response({"ok": True})


async def handle_end(request: web.Request) -> web.Response:
    body = await request.json()
    call_sid = (body.get("callSid") or "").strip()

    async with _LOCK:
        entry = _SESSIONS.pop(call_sid, None)

    if entry:
        try:
            await entry["copilot"].on_call_end()
        except Exception as e:
            logger.error("copilot.on_call_end failed | callSid=%s error=%s", call_sid, e)
        logger.info("Demo call ended | callSid=%s", call_sid)

    return web.json_response({"ok": True, "found": entry is not None})


async def handle_health(_: web.Request) -> web.Response:
    return web.json_response({"status": "ok", "activeCalls": len(_SESSIONS)})


async def _cleanup(_: web.Application):
    global _http_session
    if _http_session and not _http_session.closed:
        await _http_session.close()
        _http_session = None


def create_app() -> web.Application:
    app = web.Application()
    app.router.add_post("/demo/start", handle_start)
    app.router.add_post("/demo/utterance", handle_utterance)
    app.router.add_post("/demo/end", handle_end)
    app.router.add_get("/healthz", handle_health)
    app.on_cleanup.append(_cleanup)
    return app


def main():
    logger.info("Demo runner listening on %s:%s | backend=%s", HOST, PORT, BACKEND_URL)
    web.run_app(create_app(), host=HOST, port=PORT, print=None)


if __name__ == "__main__":
    main()
