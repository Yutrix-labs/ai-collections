"""
ws_telephony_bridge.py

Bridges Tata Smartflo's bidirectional VOICE-streaming WebSocket into a LiveKit room — the
WebSocket replacement for a SIP trunk. This is the "VOICE Bot" Tata connects to.

FLOW (full Exotel replacement):
  1. Frontend hits POST /collassistantapi/call/start (call.mode=tata).
  2. Spring backend: creates room `call-<agreementId>`, dispatches the listening agent into it,
     mints the human-agent browser link (meetUrl), then calls Tata "Click to Call Support"
     (customer-first: Tata rings the CUSTOMER).
  3. Customer answers → Tata routes the call to the VOICE Bot configured against the API key in
     the portal → that's THIS bridge's WebSocket URL.
  4. Tata sends `start` carrying callSid / streamSid / from / to. Because Tata's WS URL is STATIC
     (portal-configured, so it cannot carry room/sessionId), we resolve the session from the phone
     number via GET /call/by-mobile/{mobile}, then join THAT room as `customer_<sessionId>`
     (the "customer_" prefix makes the existing agent treat us as the customer — `_is_customer()`).
  5. Audio flows both ways: customer phone ⇄ human agent's browser, live transcript to the FE.

PROTOCOL (verified against Tata's spec — it is Twilio Media Streams compatible):
  https://docs.smartflo.tatatelebusiness.com/docs/bi-directional-audio-streaming-integration-document
  Inbound (Tata → us):  connected | start | media | stop | dtmf | mark
  Outbound (us → Tata): {"event":"media","streamSid":"<sid>","media":{"payload":"<b64>","chunk":N}}
                        — streamSid is REQUIRED; payload must be >=160 bytes / multiples of 160.
  Audio: audio/x-mulaw (G.711 µ-law), 8000 Hz, 8-bit.

ADDITIVE ONLY: does not modify silent_transcriber_agent.py or any existing module. Deploy as a
sibling process (see k8s/ws-bridge/).
"""

import asyncio
import base64
import json
import logging
import os
import uuid
from array import array
from typing import Optional

import aiohttp
from aiohttp import web, WSMsgType
from dotenv import load_dotenv
from livekit import api, rtc

load_dotenv(".env")

logger = logging.getLogger("ws-telephony-bridge")
logging.basicConfig(level=logging.INFO)

# --------------------------------------------------------------------------------------
# Config  (LIVEKIT_* / AGENT_NAME / BACKEND_URL are the SAME vars the listening agent uses)
# --------------------------------------------------------------------------------------
LIVEKIT_URL = os.getenv("LIVEKIT_URL", "")
LIVEKIT_API_KEY = os.getenv("LIVEKIT_API_KEY", "")
LIVEKIT_API_SECRET = os.getenv("LIVEKIT_API_SECRET", "")
AGENT_NAME = os.getenv("AGENT_NAME", "silent-transcriber")
BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8080")
BACKEND_API_KEY = os.getenv("BACKEND_API_KEY", "").strip()

WS_BRIDGE_HOST = os.getenv("WS_BRIDGE_HOST", "0.0.0.0")
WS_BRIDGE_PORT = int(os.getenv("WS_BRIDGE_PORT", "8090"))
# Shared secret Tata echoes back as ?token=... Always set in any reachable deployment.
WS_BRIDGE_AUTH_TOKEN = os.getenv("WS_BRIDGE_AUTH_TOKEN", "")

# Identity whose audio is streamed back down to the phone (the tele-caller's browser leg).
BRIDGE_AGENT_IDENTITY = os.getenv("BRIDGE_AGENT_IDENTITY", "human-agent")
# Fallback when the by-mobile lookup finds no session (e.g. a Tata test call with no /call/start):
# mint our own room and dispatch the agent so audio is still transcribed. Handy for smoke tests.
BRIDGE_DISPATCH_AGENT = os.getenv("BRIDGE_DISPATCH_AGENT", "false").lower() == "true"

# Tata's verified media format. Override only if their spec changes.
TELEPHONY_ENCODING = os.getenv("TELEPHONY_ENCODING", "mulaw").lower()      # "mulaw" | "pcm16"
TELEPHONY_SAMPLE_RATE = int(os.getenv("TELEPHONY_SAMPLE_RATE", "8000"))
BRIDGE_PUBLISH_SAMPLE_RATE = int(os.getenv("BRIDGE_PUBLISH_SAMPLE_RATE", "16000"))
# Tata requires >=160 bytes, in multiples of 160 (160 bytes = 20ms of 8kHz mu-law).
OUT_CHUNK_BYTES = int(os.getenv("OUT_CHUNK_BYTES", "160"))
# Auto-dump this many raw inbound frames per call (schema debugging).
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
    return array("h", (_MULAW_DECODE_TABLE[b] for b in data)).tobytes()


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
# Backend session lookup (Tata's static WS URL can't carry room/sessionId — resolve by phone)
# --------------------------------------------------------------------------------------
def _backend_headers() -> dict:
    return {"X-API-KEY": BACKEND_API_KEY} if BACKEND_API_KEY else {}


async def resolve_session(mobile: str) -> Optional[dict]:
    """GET /call/by-mobile/{mobile} -> {sessionId, roomName, ...}. None if not found."""
    url = f"{BACKEND_URL}/collassistantapi/call/by-mobile/{mobile}"
    try:
        async with aiohttp.ClientSession(headers=_backend_headers()) as s:
            async with s.get(url, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                if resp.status != 200:
                    logger.warning(f"[Bridge] by-mobile lookup {resp.status} | mobile={mobile}")
                    return None
                data = (await resp.json()).get("data")
                logger.info(f"[Bridge] Session resolved | mobile={mobile} -> {data}")
                return data
    except Exception as e:
        logger.error(f"[Bridge] by-mobile lookup failed | mobile={mobile} error={e}")
        return None


async def push_call_id(session_id: str, call_sid: str, stream_sid: str = "") -> None:
    """Report Tata's call id to the backend so the session (and the next-action payload's
    `exotelCallSid`) is populated. Tata's Click to Call Support HTTP response carries no call id —
    it only arrives here, on the WebSocket `start` event."""
    if not (session_id and call_sid):
        return
    url = f"{BACKEND_URL}/collassistantapi/call/telephony-call-id"
    payload = {"sessionId": session_id, "callSid": call_sid, "streamSid": stream_sid}
    try:
        async with aiohttp.ClientSession(headers=_backend_headers()) as s:
            async with s.post(url, json=payload, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                if resp.status != 200:
                    logger.warning(f"[Bridge] call-id bind {resp.status} | sessionId={session_id}")
                else:
                    logger.info(f"[Bridge] Call id bound | sessionId={session_id} callSid={call_sid}")
    except Exception as e:
        logger.error(f"[Bridge] call-id bind failed | sessionId={session_id} error={e}")


# --------------------------------------------------------------------------------------
# One CallBridge per active call
# --------------------------------------------------------------------------------------
class CallBridge:
    def __init__(self, call_key: str, room_name: str, mobile: Optional[str],
                 ws: web.WebSocketResponse, stream_sid: str):
        self.call_key = call_key
        self.room_name = room_name
        self.mobile = mobile or call_key
        self.ws = ws
        self.stream_sid = stream_sid
        self.room = rtc.Room()
        self.source = rtc.AudioSource(sample_rate=BRIDGE_PUBLISH_SAMPLE_RATE, num_channels=1)
        self.track = rtc.LocalAudioTrack.create_audio_track("phone-audio", self.source)
        self._closed = False
        self._outbound_started = False
        self._out_buf = bytearray()
        self._chunk_no = 0

    async def maybe_dispatch_agent(self):
        """Fallback only (BRIDGE_DISPATCH_AGENT=true): no backend session, so send the agent in
        ourselves. In the normal flow /call/start already dispatched it."""
        if not BRIDGE_DISPATCH_AGENT:
            return
        async with api.LiveKitAPI(
            url=LIVEKIT_URL, api_key=LIVEKIT_API_KEY, api_secret=LIVEKIT_API_SECRET
        ) as lkapi:
            metadata = json.dumps({"mode": "livekit", "mobile": self.mobile, "sessionId": self.call_key})
            await lkapi.agent_dispatch.create_dispatch(
                api.CreateAgentDispatchRequest(agent_name=AGENT_NAME, room=self.room_name, metadata=metadata)
            )
        logger.info(f"[Bridge] Dispatched agent={AGENT_NAME} | room={self.room_name}")

    async def connect(self):
        identity = f"customer_{self.call_key}"
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

        # Forward any agent audio already published before we joined.
        for participant in self.room.remote_participants.values():
            if participant.identity != BRIDGE_AGENT_IDENTITY:
                continue
            for pub in participant.track_publications.values():
                if pub.track and pub.track.kind == rtc.TrackKind.KIND_AUDIO:
                    self._start_outbound(pub.track)

    def _on_track_subscribed(self, track, publication, participant):
        # Only the human tele-caller's audio goes back to the phone (never echo the customer).
        if track.kind == rtc.TrackKind.KIND_AUDIO and participant.identity == BRIDGE_AGENT_IDENTITY:
            self._start_outbound(track)

    def _start_outbound(self, track):
        if self._outbound_started or self._closed:
            return
        self._outbound_started = True
        logger.info(f"[Bridge] Streaming agent audio -> phone | room={self.room_name}")
        asyncio.create_task(self._pump_outbound(track))

    async def _pump_outbound(self, track):
        # AudioStream resamples the room audio down to the telephony rate for us.
        stream = rtc.AudioStream(track, sample_rate=TELEPHONY_SAMPLE_RATE, num_channels=1)
        try:
            async for event in stream:
                if self._closed:
                    break
                pcm16 = bytes(event.frame.data)
                payload = pcm16_to_mulaw(pcm16) if TELEPHONY_ENCODING == "mulaw" else pcm16
                await self._send_media(payload)
        except Exception as e:
            logger.error(f"[Bridge] Outbound pump error | room={self.room_name} error={e}")
        finally:
            await stream.aclose()

    async def push_inbound(self, raw_audio: bytes):
        """raw_audio: bytes as received from Tata (TELEPHONY_ENCODING, 8kHz)."""
        pcm16 = mulaw_to_pcm16(raw_audio) if TELEPHONY_ENCODING == "mulaw" else raw_audio
        pcm16 = resample_pcm16(pcm16, TELEPHONY_SAMPLE_RATE, BRIDGE_PUBLISH_SAMPLE_RATE)
        samples = len(pcm16) // 2
        if samples == 0:
            return
        frame = rtc.AudioFrame(
            data=pcm16, sample_rate=BRIDGE_PUBLISH_SAMPLE_RATE, num_channels=1, samples_per_channel=samples
        )
        await self.source.capture_frame(frame)

    async def _send_media(self, payload: bytes):
        """Buffer and emit in >=160-byte multiples with the streamSid, per Tata's spec."""
        if self._closed or self.ws.closed:
            return
        self._out_buf.extend(payload)
        while len(self._out_buf) >= OUT_CHUNK_BYTES:
            chunk = bytes(self._out_buf[:OUT_CHUNK_BYTES])
            del self._out_buf[:OUT_CHUNK_BYTES]
            self._chunk_no += 1
            try:
                await self.ws.send_str(json.dumps({
                    "event": "media",
                    "streamSid": self.stream_sid,
                    "media": {
                        "payload": base64.b64encode(chunk).decode("ascii"),
                        "chunk": self._chunk_no,
                    },
                }))
            except Exception as e:
                logger.warning(f"[Bridge] send failed | error={e}")
                return

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
def _pick_customer_number(start: dict) -> Optional[str]:
    """Tata's start carries from/to. Click-to-Call-Support is outbound to the customer, so `to`
    is normally the customer and `from` the DID — but fall back across both plus customParameters.
    The backend matches on the last 10 digits, so country codes are fine."""
    custom = start.get("customParameters") or {}
    for candidate in (custom.get("mobile"), custom.get("customer_number"), start.get("to"), start.get("from")):
        if candidate and str(candidate).strip():
            return str(candidate).strip()
    return None


async def telephony_ws_handler(request: web.Request) -> web.WebSocketResponse:
    if WS_BRIDGE_AUTH_TOKEN and request.query.get("token") != WS_BRIDGE_AUTH_TOKEN:
        raise web.HTTPUnauthorized(text="invalid or missing token")

    path_id = request.match_info.get("call_id") or uuid.uuid4().hex
    ws = web.WebSocketResponse(heartbeat=20)
    await ws.prepare(request)
    logger.info(f"[Bridge] WS connected | path={path_id} query={dict(request.query)}")

    bridge: Optional[CallBridge] = None
    frames_logged = 0

    try:
        async for msg in ws:
            if msg.type in (WSMsgType.ERROR, WSMsgType.CLOSE, WSMsgType.CLOSING):
                break
            if msg.type != WSMsgType.TEXT:
                continue

            # Dump the first few raw frames (schema debugging / vendor drift).
            if frames_logged < LOG_FIRST_N_FRAMES:
                frames_logged += 1
                logger.info(f"[Bridge] RAW inbound #{frames_logged} | {msg.data[:400]}")

            try:
                data = json.loads(msg.data)
            except (ValueError, TypeError):
                continue

            event = data.get("event")

            if event == "connected":
                logger.info("[Bridge] Tata handshake: connected")

            elif event == "start":
                start = data.get("start") or {}
                stream_sid = data.get("streamSid") or start.get("streamSid") or ""
                call_sid = start.get("callSid")
                mobile = _pick_customer_number(start)
                fmt = start.get("mediaFormat") or {}
                logger.info(
                    f"[Bridge] START | callSid={call_sid} streamSid={stream_sid} "
                    f"from={start.get('from')} to={start.get('to')} mobile={mobile} "
                    f"format={fmt.get('encoding')}@{fmt.get('sampleRate')}"
                )

                # Resolve the room the backend already created for this customer.
                session = await resolve_session(mobile) if mobile else None
                if session and session.get("roomName"):
                    room_name = session["roomName"]
                    call_key = session.get("sessionId") or path_id
                    # Tata's HTTP response has no call id — bind the one from this start event so
                    # the session / next-action payload carries it instead of null.
                    if call_sid:
                        await push_call_id(session.get("sessionId"), call_sid, stream_sid)
                elif BRIDGE_DISPATCH_AGENT:
                    room_name = f"ws-call-{path_id}"
                    call_key = path_id
                    logger.warning(
                        f"[Bridge] No session for mobile={mobile} — standalone fallback room={room_name}"
                    )
                else:
                    logger.error(
                        f"[Bridge] No session for mobile={mobile} and BRIDGE_DISPATCH_AGENT=false — "
                        f"closing. Was /call/start called for this customer?"
                    )
                    break

                bridge = CallBridge(call_key, room_name, mobile, ws, stream_sid)
                await bridge.maybe_dispatch_agent()
                await bridge.connect()

            elif event == "media":
                if bridge is None:
                    continue  # media before start — ignore
                payload_b64 = (data.get("media") or {}).get("payload")
                if payload_b64:
                    await bridge.push_inbound(base64.b64decode(payload_b64))

            elif event == "dtmf":
                logger.info(f"[Bridge] DTMF | digit={(data.get('dtmf') or {}).get('digit')}")

            elif event == "stop":
                reason = (data.get("stop") or {}).get("reason")
                logger.info(f"[Bridge] STOP | reason={reason}")
                break

    finally:
        if bridge:
            await bridge.close()
        logger.info(f"[Bridge] WS closed | path={path_id}")
    return ws


def create_app() -> web.Application:
    app = web.Application()
    app.router.add_get("/telephony/stream/{call_id}", telephony_ws_handler)
    # Tata's portal may be configured without a trailing path segment — accept both.
    app.router.add_get("/telephony/stream", telephony_ws_handler)
    app.router.add_get("/healthz", lambda _: web.json_response({"status": "ok"}))
    return app


def main():
    if not (LIVEKIT_URL and LIVEKIT_API_KEY and LIVEKIT_API_SECRET):
        raise SystemExit("LIVEKIT_URL / LIVEKIT_API_KEY / LIVEKIT_API_SECRET must be set")
    logger.info(
        f"Bridge on {WS_BRIDGE_HOST}:{WS_BRIDGE_PORT} | backend={BACKEND_URL} "
        f"| dispatch_agent={BRIDGE_DISPATCH_AGENT} | {TELEPHONY_ENCODING}@{TELEPHONY_SAMPLE_RATE}"
    )
    web.run_app(create_app(), host=WS_BRIDGE_HOST, port=WS_BRIDGE_PORT)


if __name__ == "__main__":
    main()
