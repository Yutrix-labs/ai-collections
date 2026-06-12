"""Gemini Live Translate bridge: one persistent WebSocket session that turns a
stream of source-language PCM audio into target-language PCM audio.

The bridge is transport-only. It does NOT join the LiveKit room — the caller
feeds it source frames (already subscribed elsewhere) via ``push_frame`` and
provides an ``rtc.AudioSource`` that the bridge captures translated audio into.

Wire protocol (raw BidiGenerateContent WebSocket), confirmed against
google-gemini/gemini-live-api-examples:

  client -> setup ............ model + translationConfig(targetLanguageCode)
  server -> setupComplete
  client -> realtimeInput .... base64 PCM 16kHz mono
  server -> serverContent .... modelTurn.parts[].inlineData.data = PCM 24kHz mono
                               inputTranscription  (source text + detected lang)
                               outputTranscription (translated text)

We use raw aiohttp WebSockets (already a dependency) rather than the google-genai
SDK so the existing Vertex AI path (which pins google-genai 1.x) is untouched.
"""

import asyncio
import base64
import json
import logging
import os

import aiohttp
from livekit import rtc

logger = logging.getLogger("translation.bridge")

GEMINI_LIVE_URL = (
    "wss://generativelanguage.googleapis.com/ws/"
    "google.ai.generativelanguage.v1beta.GenerativeService.BidiGenerateContent"
)
GEMINI_MODEL = "gemini-3.5-live-translate-preview"

# Gemini Live Translate audio formats (fixed by the API).
INPUT_SAMPLE_RATE = 16000   # what we send
OUTPUT_SAMPLE_RATE = 24000  # what we receive
NUM_CHANNELS = 1

# Batch input audio into ~100ms chunks before sending (Google's recommended
# chunk size). Sending every ~10ms LiveKit frame individually floods the event
# loop with JSON+base64 work (~100/s per bridge) and starves the agent — that
# overload is what drops the LiveKit/Deepgram/Gemini sockets. 100ms = ~10x fewer
# sends. 16-bit mono: 16000 * 2 bytes * 0.1s.
INPUT_CHUNK_BYTES = int(INPUT_SAMPLE_RATE * 2 * 0.1)
# Cap buffered translated chunks so a backlog can't grow latency unbounded;
# drop oldest beyond this (bounded latency > perfect audio on a live call).
MAX_OUT_QUEUE = 200

# Turn-detection tuning — the dominant latency lever. Gemini waits this many ms
# of silence before deciding a turn ended and emitting the translation; the
# ~800ms default adds ~0.8s to every turn. 500ms is the recommended floor (below
# ~200ms it fragments mid-sentence). Tunable via env so it can be felt on a real
# call without code edits. HIGH sensitivity commits the start/end of speech
# faster than LOW.
VAD_SILENCE_MS = int(os.getenv("TRANSLATION_SILENCE_MS", "500"))
VAD_PREFIX_PADDING_MS = int(os.getenv("TRANSLATION_PREFIX_MS", "20"))


class TranslationBridge:
    """One translation direction (source auto-detected -> target_language)."""

    def __init__(
        self,
        name: str,
        target_language: str,
        api_key: str,
        audio_source: rtc.AudioSource,
        on_detected_language=None,
        on_turn=None,
    ):
        """
        name: short label for logs (e.g. "customer->agent").
        target_language: BCP-47 code Gemini translates INTO (output language).
        audio_source: rtc.AudioSource (24kHz mono) that translated audio is
            captured into. The caller publishes the matching LocalAudioTrack.
        on_detected_language: optional callable(code) invoked once, the first
            time Gemini reports the detected SOURCE language of the input audio.
        on_turn: optional callable(source_text, source_lang, translated_text,
            target_lang) invoked once per completed turn (on turnComplete) with
            the full original + translated text. Used to mirror translated text
            into the agent UI in near-real-time.
        """
        self.name = name
        self.target_language = target_language
        self._api_key = api_key
        self._audio_source = audio_source
        self._on_detected_language = on_detected_language
        self._on_turn = on_turn

        self._session: aiohttp.ClientSession | None = None
        self._ws: aiohttp.ClientWebSocketResponse | None = None
        self._setup_complete = asyncio.Event()
        self._closed = False
        self._detected_language: str | None = None

        # Per-turn transcript accumulation — Gemini streams partial input/output
        # transcription chunks, finalised by turnComplete. We buffer and emit one
        # clean paired turn instead of flooding the UI with fragments.
        self._src_buf = ""
        self._out_buf = ""
        self._turn_src_lang: str | None = None

        # Reconnect diagnostics: distinguish a normal GoAway (audio was flowing)
        # from a rejected setup (closed before any audio) so we can back off and
        # log the real reason instead of flooding.
        self._got_audio_this_session = False
        self._setup_failures = 0

        # Accumulate input frames into ~100ms chunks before sending to Gemini.
        self._in_buf = bytearray()

        # Serialise capture into the AudioSource so frames play in order. Bounded
        # so a slow playout can't accumulate latency without limit.
        self._out_queue: asyncio.Queue[bytes] = asyncio.Queue(maxsize=MAX_OUT_QUEUE)
        self._tasks: list[asyncio.Task] = []

    async def start(self) -> None:
        """Open the WebSocket, send setup, and start the receive/playout loops."""
        self._session = aiohttp.ClientSession()
        await self._connect()
        self._tasks.append(asyncio.create_task(self._receive_loop()))
        self._tasks.append(asyncio.create_task(self._playout_loop()))
        logger.info(f"[{self.name}] bridge started | target={self.target_language}")

    async def _connect(self) -> None:
        self._got_audio_this_session = False
        url = f"{GEMINI_LIVE_URL}?key={self._api_key}"
        self._ws = await self._session.ws_connect(url, heartbeat=20)
        setup = {
            "setup": {
                "model": f"models/{GEMINI_MODEL}",
                "inputAudioTranscription": {},
                "outputAudioTranscription": {},
                "generationConfig": {
                    "responseModalities": ["AUDIO"],
                    "translationConfig": {
                        "targetLanguageCode": self.target_language,
                        "echoTargetLanguage": True,
                    },
                },
                "realtimeInputConfig": {
                    "automaticActivityDetection": {
                        "disabled": False,
                        "startOfSpeechSensitivity": "START_SENSITIVITY_HIGH",
                        "endOfSpeechSensitivity": "END_SENSITIVITY_HIGH",
                        "prefixPaddingMs": VAD_PREFIX_PADDING_MS,
                        "silenceDurationMs": VAD_SILENCE_MS,
                    },
                },
            }
        }
        await self._ws.send_str(json.dumps(setup))
        logger.info(f"[{self.name}] setup sent, awaiting setupComplete")

    async def push_frame(self, frame: rtc.AudioFrame) -> None:
        """Feed one source-audio frame (16kHz mono) to Gemini.

        Frames are buffered and flushed in ~100ms chunks to keep per-frame
        JSON/base64/send overhead off the hot path (~10 sends/s instead of ~100).
        """
        if self._closed or self._ws is None or not self._setup_complete.is_set():
            # Drop buffered audio while disconnected so it can't go stale.
            if self._in_buf:
                self._in_buf.clear()
            return
        self._in_buf += bytes(frame.data)  # int16 LE PCM
        if len(self._in_buf) >= INPUT_CHUNK_BYTES:
            await self._flush_input()

    async def _flush_input(self) -> None:
        if not self._in_buf or self._ws is None:
            return
        pcm = bytes(self._in_buf)
        self._in_buf.clear()
        try:
            payload = {
                "realtimeInput": {
                    "audio": {
                        "mimeType": f"audio/pcm;rate={INPUT_SAMPLE_RATE}",
                        "data": base64.b64encode(pcm).decode("ascii"),
                    }
                }
            }
            await self._ws.send_str(json.dumps(payload))
        except Exception as e:
            logger.error(f"[{self.name}] flush_input error: {e}")

    async def _receive_loop(self) -> None:
        while not self._closed:
            try:
                async for msg in self._ws:
                    if msg.type == aiohttp.WSMsgType.TEXT:
                        self._handle_message(json.loads(msg.data))
                    elif msg.type == aiohttp.WSMsgType.BINARY:
                        self._handle_message(json.loads(msg.data.decode("utf-8")))
                    elif msg.type in (
                        aiohttp.WSMsgType.CLOSED,
                        aiohttp.WSMsgType.ERROR,
                    ):
                        break
            except Exception as e:
                logger.error(f"[{self.name}] receive loop error: {e}")

            if self._closed:
                break

            # Surface WHY Gemini closed — without this a bad config (e.g. an
            # unsupported targetLanguageCode) just looks like an endless retry.
            close_code = getattr(self._ws, "close_code", None)
            ws_exc = self._ws.exception() if self._ws else None
            session_audio = self._got_audio_this_session

            if not session_audio:
                # Closed before producing any translated audio. Almost always a
                # rejected setup (bad language code / model / key), not a normal
                # GoAway. Count these and back off so we don't flood.
                self._setup_failures += 1
            else:
                self._setup_failures = 0

            if self._setup_failures >= 3 and not session_audio:
                logger.error(
                    f"[{self.name}] Gemini closed {self._setup_failures}x with no audio "
                    f"(close_code={close_code}, exc={ws_exc}). Likely an invalid "
                    f"targetLanguageCode='{self.target_language}', model, or API key."
                )
            else:
                logger.warning(
                    f"[{self.name}] WS closed (close_code={close_code}, "
                    f"got_audio={session_audio}); reconnecting"
                )

            # Exponential backoff capped at 30s (1,2,4,8,16,30...).
            delay = min(30, 2 ** min(self._setup_failures, 5)) if not session_audio else 1
            self._setup_complete.clear()
            await asyncio.sleep(delay)
            try:
                await self._connect()
            except Exception as e:
                logger.error(f"[{self.name}] reconnect failed: {e}")
                await asyncio.sleep(2)

    def _handle_message(self, message: dict) -> None:
        if "setupComplete" in message:
            self._setup_complete.set()
            logger.info(f"[{self.name}] setup complete")
            return

        server_content = message.get("serverContent")
        if not server_content:
            return

        # Translated audio -> queue for ordered playout.
        model_turn = server_content.get("modelTurn")
        if model_turn:
            for part in model_turn.get("parts", []):
                inline = part.get("inlineData")
                if inline and inline.get("data"):
                    self._got_audio_this_session = True
                    self._enqueue_audio(base64.b64decode(inline["data"]))

        # Source transcript carries the auto-detected source language.
        in_tx = server_content.get("inputTranscription")
        if in_tx:
            lang = in_tx.get("languageCode")
            if lang:
                self._turn_src_lang = lang
                if self._detected_language is None:
                    self._detected_language = lang
                    logger.info(f"[{self.name}] detected source language: {lang}")
                    if self._on_detected_language:
                        try:
                            self._on_detected_language(lang)
                        except Exception as e:
                            logger.error(f"[{self.name}] on_detected_language error: {e}")
            if in_tx.get("text"):
                self._src_buf += in_tx["text"]

        out_tx = server_content.get("outputTranscription")
        if out_tx and out_tx.get("text"):
            self._out_buf += out_tx["text"]

        # turnComplete finalises the accumulated transcripts → emit one paired turn.
        if server_content.get("turnComplete"):
            self._emit_turn()

    def _emit_turn(self) -> None:
        source = self._src_buf.strip()
        translated = self._out_buf.strip()
        src_lang = self._turn_src_lang
        self._src_buf = ""
        self._out_buf = ""
        if (source or translated) and self._on_turn:
            try:
                self._on_turn(source, src_lang, translated, self.target_language)
            except Exception as e:
                logger.error(f"[{self.name}] on_turn error: {e}")

    def _enqueue_audio(self, pcm: bytes) -> None:
        """Queue translated PCM for playout, dropping the oldest if we're behind."""
        try:
            self._out_queue.put_nowait(pcm)
        except asyncio.QueueFull:
            try:
                self._out_queue.get_nowait()
            except asyncio.QueueEmpty:
                pass
            try:
                self._out_queue.put_nowait(pcm)
            except asyncio.QueueFull:
                pass

    async def _playout_loop(self) -> None:
        """Capture translated PCM into the AudioSource in arrival order.

        AudioSource.capture_frame paces playout to real time, so awaiting it
        sequentially provides natural back-pressure without frame pile-up.
        """
        while not self._closed:
            try:
                pcm = await self._out_queue.get()
                samples = len(pcm) // 2  # int16 mono
                if samples == 0:
                    continue
                frame = rtc.AudioFrame(
                    data=pcm,
                    sample_rate=OUTPUT_SAMPLE_RATE,
                    num_channels=NUM_CHANNELS,
                    samples_per_channel=samples,
                )
                await self._audio_source.capture_frame(frame)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"[{self.name}] playout error: {e}")

    async def aclose(self) -> None:
        self._closed = True
        for t in self._tasks:
            t.cancel()
        if self._ws is not None and not self._ws.closed:
            await self._ws.close()
        if self._session is not None and not self._session.closed:
            await self._session.close()
        logger.info(f"[{self.name}] bridge closed")
