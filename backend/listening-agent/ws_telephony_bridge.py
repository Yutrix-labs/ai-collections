"""
ws_telephony_bridge.py

Bridges a telephony provider (Tata Smartflo) that streams call audio over a *bidirectional*
WebSocket into a LiveKit room — the WebSocket replacement for a SIP trunk.

INTEGRATED FLOW (how it is used in the demo):
  1. Frontend hits  POST /collassistantapi/call/start  (call.mode=tata).
  2. The Spring backend creates the LiveKit room `call-<agreementId>`, dispatches the existing
     listening agent into it, mints the human-agent browser link (meetUrl), and triggers the
     Tata click-to-call to the customer — handing Tata THIS bridge's WebSocket URL, which
     carries `room`, `sessionId` and `mobile` as query params.
  3. When the customer answers, Tata opens a WebSocket to this bridge. The bridge JOINS THE
     SAME room `call-<agreementId>` as participant `customer_<sessionId>` (the "customer_"
     prefix makes the existing agent treat it exactly like a browser-joined customer — see
     `_is_customer()` in silent_transcriber_agent.py), then pipes audio both ways:
       - customer phone audio  (Tata WS -> LiveKit room, published as the customer track)
       - human-agent audio     (LiveKit room -> Tata WS, so the customer hears the agent)

Because the bridge reuses the room + sessionId the backend already created, the human agent
(in the browser) and the customer (on the phone) share ONE room in real time, and transcription
/ copilot / disposition keep working unchanged. This bridge does NOT dispatch its own agent in
the integrated flow (the backend already did) — set BRIDGE_DISPATCH_AGENT=true only for
standalone testing without the backend.

ADDITIVE ONLY: does not modify silent_transcriber_agent.py or any existing module. Deploy as a
sibling process (its own container / ngrok tunnel), not a replacement for the agent worker.

!! CONFIRM AGAINST TATA'S SPEC before a real call:
   * The JSON envelope of Tata's WS frames (event/field names). The parser below assumes a
     generic Twilio-Media-Streams-style shape; the first real call auto-logs the raw frames
     (see LOG_FIRST_N_FRAMES) so you can map their actual schema.
   * The codec + sample rate Tata sends (default: 8kHz mu-law / G.711 — the telephony norm).
"""

import asyncio
import base64
import json
import logging
import os
import uuid
from array import array
from typing import Optional
from urllib.parse import urlencode

from aiohttp import web, WSMsgType
from dotenv import load_dotenv
from livekit import api, rtc

load_dotenv(".env")

logger = logging.getLogger("ws-telephony-bridge")
logging.basicConfig(level=logging.INFO)

# --------------------------------------------------------------------------------------
# Config  (LIVEKIT_* / AGENT_NAME are the SAME vars the listening agent already uses)
# --------------------------------------------------------------------------------------
LIVEKIT_URL = os.getenv("LIVEKIT_URL", "")
LIVEKIT_API_KEY = os.getenv("LIVEKIT_API_KEY", "")
LIVEKIT_API_SECRET = os.getenv("LIVEKIT_API_SECRET", "")
AGENT_NAME = os.getenv("AGENT_NAME", "silent-transcriber")

WS_BRIDGE_HOST = os.getenv("WS_BRIDGE_HOST", "0.0.0.0")
WS_BRIDGE_PORT = int(os.getenv("WS_BRIDGE_PORT", "8090"))
# Shared secret Tata must echo back as ?token=... on every connection. Always set in any
# reachable deployment; leave blank only for a purely-local test.
WS_BRIDGE_AUTH_TOKEN = os.getenv("WS_BRIDGE_AUTH_TOKEN", "")
# Public base URL this bridge is reachable at (ngrok URL for testing). Only used to build the
# example URL logged at startup; in the integrated flow the BACKEND builds the URL it hands Tata.
PUBLIC_BRIDGE_BASE_URL = os.getenv("PUBLIC_BRIDGE_BASE_URL", "wss://voice-bridge.example.com")

# Identity whose audio is streamed back down to the phone (the tele-caller's browser leg).
BRIDGE_AGENT_IDENTITY = os.getenv("BRIDGE_AGENT_IDENTITY", "human-agent")
# In the integrated flow the backend dispatches the agent; keep this false. Set true only for
# standalone testing (no backend) so the bridge dispatches the agent itself.
BRIDGE_DISPATCH_AGENT = os.getenv("BRIDGE_DISPATCH_AGENT", "false").lower() == "true"

TELEPHONY_ENCODING = os.getenv("TELEPHONY_ENCODING", "mulaw").lower()      # "mulaw" | "pcm16"
TELEPHONY_SAMPLE_RATE = int(os.getenv("TELEPHONY_SAMPLE_RATE", "8000"))    # provider's native rate
TELEPHONY_WS_FRAMING = os.getenv("TELEPHONY_WS_FRAMING", "json").lower()   # "json" | "raw"
BRIDGE_PUBLISH_SAMPLE_RATE = int(os.getenv("BRIDGE_PUBLISH_SAMPLE_RATE", "16000"))
# Auto-dump this many raw inbound frames per call so you can reverse-engineer Tata's real schema.
LOG_FIRST_N_FRAMES = int(os.getenv("LOG_FIRST_N_FRAMES", "5"))


# --------------------------------------------------------------------------------------
# G.711 mu-law <-> 16-bit PCM (audioop is gone in Python 3.13; implement ITU-T G.711 directly)
# --------------------------------------------------------------------------------------
_MULAW_BIAS = 0x84
_MULAW_CLIP = 32635


def _mulaw_decode_sample(u_val: int) -> int:
    u_val = ~u_val & 0xFF
    sign = u_val & 0x80
    exponent = (u_val >> 4) & 0x07
    mantissa = u_val & 0x0F
    sample = ((mantissa << 3) + _MULAW_BIAS) << exponent
    sample -= _MULAW_BIAS
    return -sample if sign else sample


def _mulaw_encode_sample(sample: int) -> int:
    sign = 0
    if sample < 0:
        sample = -sample
        sign = 0x80
    sample = min(sample + _MULAW_BIAS, _MULAW_CLIP)
    exponent = 7
    mask = 0x4000
    while exponent > 0 and not (sample & mask):
        exponent -= 1
        mask >>= 1
    mantissa = (sample >> (exponent + 3)) & 0x0F
    return ~(sign | (exponent << 4) | mantissa) & 0xFF


_MULAW_DECODE_TABLE = [_mulaw_decode_sample(i) for i in range(256)]


def mulaw_to_pcm16(data: bytes) -> bytes:
    out = array("h", (_MULAW_DECODE_TABLE[b] for b in data))
    return out.tobytes()


def pcm16_to_mulaw(data: bytes) -> bytes:
    samples = array("h")
    samples.frombytes(data)
    return bytes(_mulaw_encode_sample(s) for s in samples)


def resample_pcm16(data: bytes, src_rate: int, dst_rate: int) -> bytes:
    """Linear-interpolation resampler — adequate for voice/STT, no numpy needed."""
    if src_rate == dst_rate or not data:
        return data
    src = array("h")
    src.frombytes(data)
    n_src = len(src)
    n_dst = max(1, round(n_src * dst_rate / src_rate))
    out = array("h", [0]) * n_dst
    for i in range(n_dst):
        pos = i * (n_src - 1) / max(1, n_dst - 1) if n_dst > 1 else 0
        lo = int(pos)
        hi = min(lo + 1, n_src - 1)
        frac = pos - lo
        out[i] = int(src[lo] * (1 - frac) + src[hi] * frac)
    return out.tobytes()


# --------------------------------------------------------------------------------------
# One CallBridge per active call
# --------------------------------------------------------------------------------------
class CallBridge:
    def __init__(self, call_id: str, room_name: str, mobile: Optional[str], ws: web.WebSocketResponse):
        self.call_id = call_id
        self._room_name = room_name
        self.mobile = mobile or call_id
        self.ws = ws
        self.room = rtc.Room()
        self.source = rtc.AudioSource(sample_rate=BRIDGE_PUBLISH_SAMPLE_RATE, num_channels=1)
        self.track = rtc.LocalAudioTrack.create_audio_track("phone-audio", self.source)
        self._closed = False
        self._outbound_started = False  # only forward ONE agent track to the phone
        self._inbound_frames_logged = 0

    @property
    def room_name(self) -> str:
        return self._room_name

    async def maybe_dispatch_agent(self):
        """Standalone-test only: dispatch the existing agent into the room. In the integrated
        flow the backend already dispatched it, so this is skipped (BRIDGE_DISPATCH_AGENT=false)."""
        if not BRIDGE_DISPATCH_AGENT:
            return
        async with api.LiveKitAPI(
            url=LIVEKIT_URL, api_key=LIVEKIT_API_KEY, api_secret=LIVEKIT_API_SECRET
        ) as lkapi:
            metadata = json.dumps({"mode": "livekit", "mobile": self.mobile, "sessionId": self.call_id})
            await lkapi.agent_dispatch.create_dispatch(
                api.CreateAgentDispatchRequest(agent_name=AGENT_NAME, room=self.room_name, metadata=metadata)
            )
        logger.info(f"[Bridge] Dispatched agent={AGENT_NAME} | room={self.room_name}")

    async def connect(self):
        identity = f"customer_{self.call_id}"
        token = (
            api.AccessToken(LIVEKIT_API_KEY, LIVEKIT_API_SECRET)
            .with_identity(identity)
            .with_grants(
                api.VideoGrants(room_join=True, room=self.room_name, can_publish=True, can_subscribe=True)
            )
            .to_jwt()
        )
        self.room.on("track_subscribed", self._on_track_subscribed)
        await self.room.connect(LIVEKIT_URL, token, rtc.RoomOptions(auto_subscribe=True))
        await self.room.local_participant.publish_track(self.track)
        logger.info(f"[Bridge] Joined room={self.room_name} as {identity} | mobile={self.mobile}")

        # Forward any agent audio track that was already published before we joined.
        for participant in self.room.remote_participants.values():
            if participant.identity != BRIDGE_AGENT_IDENTITY:
                continue
            for pub in participant.track_publications.values():
                if pub.track and pub.track.kind == rtc.TrackKind.KIND_AUDIO:
                    self._start_outbound(pub.track)

    def _on_track_subscribed(self, track, publication, participant):
        # Only stream the human tele-caller's audio back to the phone (ignore other tracks so
        # we never double-send or echo the customer's own audio).
        if track.kind == rtc.TrackKind.KIND_AUDIO and participant.identity == BRIDGE_AGENT_IDENTITY:
            self._start_outbound(track)

    def _start_outbound(self, track: "rtc.RemoteAudioTrack"):
        if self._outbound_started or self._closed:
            return
        self._outbound_started = True
        logger.info(f"[Bridge] Streaming agent audio -> phone | room={self.room_name}")
        asyncio.create_task(self._pump_outbound(track))

    async def _pump_outbound(self, track: "rtc.RemoteAudioTrack"):
        # AudioStream resamples the room audio down to the telephony rate for us.
        stream = rtc.AudioStream(track, sample_rate=TELEPHONY_SAMPLE_RATE, num_channels=1)
        try:
            async for event in stream:
                if self._closed:
                    break
                pcm16 = bytes(event.frame.data)
                payload = pcm16_to_mulaw(pcm16) if TELEPHONY_ENCODING == "mulaw" else pcm16
                await self._send_to_provider(payload)
        finally:
            await stream.aclose()

    async def push_inbound(self, raw_audio: bytes):
        """raw_audio: bytes exactly as received from Tata (in TELEPHONY_ENCODING)."""
        pcm16 = mulaw_to_pcm16(raw_audio) if TELEPHONY_ENCODING == "mulaw" else raw_audio
        pcm16 = resample_pcm16(pcm16, TELEPHONY_SAMPLE_RATE, BRIDGE_PUBLISH_SAMPLE_RATE)
        samples = len(pcm16) // 2
        if samples == 0:
            return
        frame = rtc.AudioFrame(
            data=pcm16, sample_rate=BRIDGE_PUBLISH_SAMPLE_RATE, num_channels=1, samples_per_channel=samples
        )
        await self.source.capture_frame(frame)

    async def _send_to_provider(self, payload: bytes):
        if self._closed or self.ws.closed:
            return
        if TELEPHONY_WS_FRAMING == "raw":
            await self.ws.send_bytes(payload)
        else:
            # Generic Twilio-Media-Streams-style envelope — ADJUST to Tata's outbound schema.
            await self.ws.send_str(json.dumps({
                "event": "media",
                "media": {"payload": base64.b64encode(payload).decode("ascii")},
            }))

    async def close(self):
        if self._closed:
            return
        self._closed = True
        try:
            await self.room.disconnect()
        except Exception:
            pass
        logger.info(f"[Bridge] Room disconnected | room={self.room_name}")


# --------------------------------------------------------------------------------------
# WebSocket endpoint Tata connects to
# --------------------------------------------------------------------------------------
def _parse_inbound_message(msg, framing: str) -> tuple[Optional[str], Optional[bytes]]:
    """Returns (event, audio_bytes). event ∈ 'start'|'media'|'stop'|None; audio only for 'media'."""
    if framing == "raw":
        if msg.type == WSMsgType.BINARY:
            return "media", msg.data
        return None, None
    if msg.type != WSMsgType.TEXT:
        return None, None
    try:
        data = json.loads(msg.data)
    except (ValueError, TypeError):
        return None, None
    event = data.get("event")
    if event == "media":
        payload_b64 = (data.get("media") or {}).get("payload")
        if payload_b64:
            return "media", base64.b64decode(payload_b64)
        return "media", None
    return event, None


async def telephony_ws_handler(request: web.Request) -> web.WebSocketResponse:
    if WS_BRIDGE_AUTH_TOKEN and request.query.get("token") != WS_BRIDGE_AUTH_TOKEN:
        raise web.HTTPUnauthorized(text="invalid or missing token")

    call_id = request.match_info.get("call_id") or uuid.uuid4().hex
    session_id = request.query.get("sessionId") or call_id
    mobile = request.query.get("mobile")
    # Integrated flow: backend passes the room it already created. Standalone: mint one.
    room_name = request.query.get("room") or f"ws-call-{call_id}"
    # Use the backend's sessionId as the participant/call key so transcripts correlate.
    call_key = session_id

    ws = web.WebSocketResponse(heartbeat=20)
    await ws.prepare(request)
    logger.info(f"[Bridge] WS connected | call_id={call_id} sessionId={session_id} room={room_name} mobile={mobile}")

    bridge = CallBridge(call_key, room_name, mobile, ws)
    try:
        await bridge.maybe_dispatch_agent()
        await bridge.connect()
    except Exception as e:
        logger.error(f"[Bridge] Setup failed | room={room_name} error={e}")
        await ws.close()
        return ws

    try:
        async for msg in ws:
            if msg.type in (WSMsgType.ERROR, WSMsgType.CLOSE, WSMsgType.CLOSING):
                break
            # Auto-log the first few raw frames so Tata's real schema can be mapped.
            if bridge._inbound_frames_logged < LOG_FIRST_N_FRAMES:
                bridge._inbound_frames_logged += 1
                preview = msg.data if isinstance(msg.data, str) else f"<{len(msg.data)} bytes binary>"
                logger.info(f"[Bridge] RAW inbound #{bridge._inbound_frames_logged} | {preview[:400]}")
            event, audio = _parse_inbound_message(msg, TELEPHONY_WS_FRAMING)
            if event == "stop":
                break
            if audio:
                await bridge.push_inbound(audio)
    finally:
        await bridge.close()
        logger.info(f"[Bridge] WS closed | call_id={call_id} room={room_name}")
    return ws


def build_provider_ws_url(call_id: Optional[str] = None, room: Optional[str] = None,
                          session_id: Optional[str] = None, mobile: Optional[str] = None) -> str:
    """Build the URL handed to Tata. In the integrated flow the SPRING BACKEND builds the
    equivalent URL (see TataService / CallController); this helper is for standalone testing.

      wss://<host>/telephony/stream/<call_id>?room=<room>&sessionId=<sid>&mobile=<phone>&token=<secret>
    """
    call_id = call_id or uuid.uuid4().hex
    params = {}
    if room:
        params["room"] = room
    if session_id:
        params["sessionId"] = session_id
    if mobile:
        params["mobile"] = mobile
    if WS_BRIDGE_AUTH_TOKEN:
        params["token"] = WS_BRIDGE_AUTH_TOKEN
    query = f"?{urlencode(params)}" if params else ""
    return f"{PUBLIC_BRIDGE_BASE_URL}/telephony/stream/{call_id}{query}"


def create_app() -> web.Application:
    app = web.Application()
    app.router.add_get("/telephony/stream/{call_id}", telephony_ws_handler)
    app.router.add_get("/healthz", lambda _: web.json_response({"status": "ok"}))
    return app


def main():
    if not (LIVEKIT_URL and LIVEKIT_API_KEY and LIVEKIT_API_SECRET):
        raise SystemExit("LIVEKIT_URL / LIVEKIT_API_KEY / LIVEKIT_API_SECRET must be set")
    logger.info(f"Bridge listening on {WS_BRIDGE_HOST}:{WS_BRIDGE_PORT} | dispatch_agent={BRIDGE_DISPATCH_AGENT}")
    logger.info("Example URL: " + build_provider_ws_url(
        call_id="demo", room="call-PL-2024-00847392", session_id="demo-session", mobile="7838153987"))
    web.run_app(create_app(), host=WS_BRIDGE_HOST, port=WS_BRIDGE_PORT)


if __name__ == "__main__":
    main()
