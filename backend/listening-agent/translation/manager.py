"""Orchestrates bidirectional translation inside an existing LiveKit room.

The listening agent is already in the room and already subscribed to both
speakers, so it publishes the two translated tracks as its OWN local tracks
(no separate bot participants needed):

    customer (any lang)  --Bridge A-->  translation-to-agent   (AGENT_LANG)
    tele-caller (AGENT_LANG) --Bridge B--> translation-to-customer (detected
                                                            customer language)

Customer language is auto-detected: Bridge A reports the detected SOURCE
language of the customer's audio, which becomes Bridge B's target so the
tele-caller's speech is mirrored back into the customer's own language.

Audio routing (so neither side hears raw + translated at once) is enforced
server-side with forced unsubscribes:

    tele-caller  hears ONLY translation-to-agent
    customer     hears ONLY translation-to-customer
"""

import asyncio
import datetime
import logging
import os

from livekit import api, rtc

from translation.gemini_bridge import (
    TranslationBridge,
    OUTPUT_SAMPLE_RATE,
    INPUT_SAMPLE_RATE,
    NUM_CHANNELS,
)

logger = logging.getLogger("translation.manager")

HUMAN_AGENT_IDENTITY = "human-agent"


class TranslationManager:
    def __init__(
        self,
        ctx,
        agent_lang: str,
        api_key: str,
        customer_lang: str | None = None,
        http_session=None,
        mobile_number: str | None = None,
        call_sid: str | None = None,
    ):
        """
        ctx: LiveKit JobContext (for ctx.room).
        agent_lang: language the tele-caller speaks/hears (Bridge A target).
        api_key: Gemini API key.
        customer_lang: explicit customer language (Bridge B target). Resolution
            order: this arg (env override) -> customer profile preferredLanguage
            -> auto-detect from the customer's first utterance. Providing it (or
            a resolvable profile) starts Bridge B immediately, removing the
            detect-then-start lag.
        http_session / mobile_number / call_sid: used to look up the customer's
            preferredLanguage and to push translated text to the backend so the
            agent UI can show it in near-real-time.
        """
        self._ctx = ctx
        self._room = ctx.room
        self._agent_lang = agent_lang
        self._api_key = api_key
        self._customer_lang = customer_lang
        self._http_session = http_session
        self._mobile_number = mobile_number
        self._call_sid = call_sid
        self._backend_url = os.getenv("BACKEND_URL", "http://localhost:8080")

        self._lkapi: api.LiveKitAPI | None = None

        # Bridge A: customer -> tele-caller (target = agent_lang)
        self._bridge_to_agent: TranslationBridge | None = None
        self._src_to_agent: rtc.AudioSource | None = None
        self._sid_to_agent: str = ""  # translation-to-agent track sid

        # Bridge B: tele-caller -> customer (target = detected customer lang)
        self._bridge_to_customer: TranslationBridge | None = None
        self._src_to_customer: rtc.AudioSource | None = None
        self._sid_to_customer: str = ""  # translation-to-customer track sid
        self._bridge_b_started = False

        # Raw human track sids / identities (filled as tracks attach).
        self._customer_identity: str | None = None
        self._customer_raw_sid: str = ""
        self._agent_raw_sid: str = ""

        self._feed_tasks: list[asyncio.Task] = []
        self._closed = False

    async def start(self) -> None:
        """Publish both translated tracks up front and open Bridge A."""
        self._lkapi = api.LiveKitAPI(
            url=os.getenv("LIVEKIT_URL", ""),
            api_key=os.getenv("LIVEKIT_API_KEY", ""),
            api_secret=os.getenv("LIVEKIT_API_SECRET", ""),
        )

        self._src_to_agent, self._sid_to_agent = await self._publish_track(
            "translation-to-agent"
        )
        self._src_to_customer, self._sid_to_customer = await self._publish_track(
            "translation-to-customer"
        )

        # Bridge A can start immediately; target language is known (agent_lang).
        self._bridge_to_agent = TranslationBridge(
            name="customer->agent",
            target_language=self._agent_lang,
            api_key=self._api_key,
            audio_source=self._src_to_agent,
            on_detected_language=self._on_customer_language_detected,
            on_turn=self._make_turn_handler("customer"),
        )
        await self._bridge_to_agent.start()

        # Resolve the customer's language up front (env override or profile) so
        # Bridge B can start immediately. Falls back to auto-detect when unknown.
        resolved = self._customer_lang or await self._fetch_customer_language()
        if resolved:
            self._bridge_b_started = True  # suppress the auto-detect path
            await self._start_bridge_to_customer(resolved)
        else:
            logger.info("Customer language unknown — will auto-detect from speech")

        # Re-enforce routing whenever a participant joins — the tele-caller and
        # SIP leg connect at different times, so the first attempt may defer one
        # side until the other is present.
        self._room.on(
            "participant_connected",
            lambda p: asyncio.create_task(self._enforce_routing()),
        )

        logger.info(
            f"TranslationManager started | agent_lang={self._agent_lang} "
            f"customer_lang={resolved or 'auto-detect'} "
            f"to_agent_sid={self._sid_to_agent} to_customer_sid={self._sid_to_customer}"
        )

    async def _fetch_customer_language(self) -> str | None:
        """Read preferredLanguage from the backend customer context, if available."""
        if not (self._http_session and self._mobile_number):
            return None
        url = (
            f"{self._backend_url}/collassistantapi/customer/"
            f"mobile/{self._mobile_number}/context"
        )
        try:
            async with self._http_session.get(url) as resp:
                if resp.status != 200:
                    logger.warning(f"Customer context lookup returned {resp.status}")
                    return None
                data = (await resp.json()).get("data", {})
                lang = (data.get("customer", {}) or {}).get("preferredLanguage")
                if lang:
                    logger.info(f"Customer preferredLanguage from profile: {lang}")
                    return lang.strip()
        except Exception as e:
            logger.error(f"Failed to fetch customer language: {e}")
        return None

    async def _publish_track(self, name: str) -> tuple[rtc.AudioSource, str]:
        # Smaller playout buffer (default is 1000ms) so translated audio doesn't
        # accumulate behind real time across a long turn. ~400ms still absorbs
        # Gemini's bursty output without underrunning.
        source = rtc.AudioSource(OUTPUT_SAMPLE_RATE, NUM_CHANNELS, queue_size_ms=400)
        track = rtc.LocalAudioTrack.create_audio_track(name, source)
        options = rtc.TrackPublishOptions()
        options.source = rtc.TrackSource.SOURCE_MICROPHONE
        publication = await self._room.local_participant.publish_track(track, options)
        logger.info(f"Published translated track '{name}' | sid={publication.sid}")
        return source, publication.sid

    # ---- track attachment (called from the entrypoint track handler) --------

    def attach_customer_track(self, track: rtc.RemoteAudioTrack, identity: str) -> None:
        """Feed the customer's audio into Bridge A (customer -> agent)."""
        self._customer_identity = identity
        self._customer_raw_sid = track.sid
        self._feed_tasks.append(
            asyncio.create_task(self._feed(track, lambda: self._bridge_to_agent))
        )
        asyncio.create_task(self._enforce_routing())
        logger.info(f"Customer track attached | identity={identity} sid={track.sid}")

    def attach_agent_track(self, track: rtc.RemoteAudioTrack, identity: str) -> None:
        """Feed the tele-caller's audio into Bridge B (agent -> customer)."""
        self._agent_raw_sid = track.sid
        self._feed_tasks.append(
            asyncio.create_task(self._feed(track, lambda: self._bridge_to_customer))
        )
        asyncio.create_task(self._enforce_routing())
        logger.info(f"Agent track attached | identity={identity} sid={track.sid}")

    async def _feed(self, track: rtc.RemoteAudioTrack, bridge_getter) -> None:
        """Resample a remote track to 16kHz mono and push frames to its bridge.

        Independent of the Deepgram transcription stream on the same track —
        LiveKit supports multiple AudioStream readers per track, so the existing
        transcription path is untouched.
        """
        audio_stream = rtc.AudioStream(
            track, sample_rate=INPUT_SAMPLE_RATE, num_channels=NUM_CHANNELS
        )
        try:
            async for event in audio_stream:
                if self._closed:
                    break
                bridge = bridge_getter()
                if bridge is not None:
                    await bridge.push_frame(event.frame)
        except Exception as e:
            logger.error(f"Feed loop error: {e}")
        finally:
            await audio_stream.aclose()

    # ---- lazy Bridge B once customer language is detected -------------------

    def _on_customer_language_detected(self, lang: str) -> None:
        if self._bridge_b_started:
            return
        self._bridge_b_started = True
        asyncio.create_task(self._start_bridge_to_customer(lang))

    async def _start_bridge_to_customer(self, customer_lang: str) -> None:
        if self._closed:
            return
        self._bridge_to_customer = TranslationBridge(
            name="agent->customer",
            target_language=customer_lang,
            api_key=self._api_key,
            audio_source=self._src_to_customer,
            on_turn=self._make_turn_handler("agent"),
        )
        await self._bridge_to_customer.start()
        logger.info(f"Bridge B started | customer_lang={customer_lang}")

    # ---- routing ------------------------------------------------------------

    async def _enforce_routing(self) -> None:
        """Force each human to hear only their translated track.

        Idempotent and resilient: each side is attempted independently and only
        when that participant is actually present in the room, so a 404 for a
        participant that hasn't joined yet (e.g. the tele-caller before the SIP
        leg connects) doesn't block the other side. Re-run as participants join.
        """
        # Tele-caller: drop the customer's raw audio + the customer-bound
        # translation; keep translation-to-agent.
        agent_drop = [s for s in (self._customer_raw_sid, self._sid_to_customer) if s]
        await self._unsubscribe(HUMAN_AGENT_IDENTITY, agent_drop)

        # Customer (SIP): drop the tele-caller's raw audio + the agent-bound
        # translation; keep translation-to-customer.
        if self._customer_identity:
            cust_drop = [s for s in (self._agent_raw_sid, self._sid_to_agent) if s]
            await self._unsubscribe(self._customer_identity, cust_drop)

    async def _unsubscribe(self, identity: str, track_sids: list[str]) -> None:
        """Force ``identity`` to unsubscribe from ``track_sids``, if present."""
        if not track_sids:
            return
        # Skip until the participant actually exists, otherwise update_subscriptions
        # returns 404. participant_connected re-runs enforcement once they join.
        if identity not in self._room.remote_participants:
            logger.info(f"Routing deferred | {identity} not in room yet")
            return
        try:
            await self._lkapi.room.update_subscriptions(
                api.UpdateSubscriptionsRequest(
                    room=self._room.name,
                    identity=identity,
                    track_sids=track_sids,
                    subscribe=False,
                )
            )
            logger.info(f"Routing enforced | {identity} unsubscribed from {track_sids}")
        except Exception as e:
            logger.error(f"Failed to enforce routing for {identity}: {e}")

    def _make_turn_handler(self, speaker: str):
        """Return an on_turn callback that mirrors a completed translated turn to
        the backend for the agent UI. ``speaker`` is who spoke the SOURCE side:
        'customer' for Bridge A (customer->agent), 'agent' for Bridge B."""

        def handler(source_text, source_lang, translated_text, target_lang):
            asyncio.create_task(
                self._push_translation(
                    speaker, source_text, source_lang, translated_text, target_lang
                )
            )

        return handler

    async def _push_translation(
        self, speaker, source_text, source_lang, translated_text, target_lang
    ):
        """POST one completed translated turn to the backend, which broadcasts it
        to the agent UI on /topic/call/{sessionId}/translation."""
        if not (self._http_session and self._call_sid):
            return
        payload = {
            "callSid": self._call_sid,
            "speaker": speaker,
            "originalText": source_text or "",
            "translatedText": translated_text or "",
            "originalLang": source_lang or "",
            "translatedLang": target_lang or "",
            "timestamp": datetime.datetime.now().strftime("%H:%M:%S"),
        }
        if self._mobile_number:
            payload["mobileNumber"] = self._mobile_number
        try:
            url = f"{self._backend_url}/collassistantapi/transcript/translation"
            async with self._http_session.post(url, json=payload) as resp:
                if resp.status != 200:
                    logger.warning(
                        f"translation push returned {resp.status}: {await resp.text()}"
                    )
        except Exception as e:
            logger.error(f"Failed to push translation: {e}")

    async def aclose(self) -> None:
        self._closed = True
        for t in self._feed_tasks:
            t.cancel()
        if self._bridge_to_agent:
            await self._bridge_to_agent.aclose()
        if self._bridge_to_customer:
            await self._bridge_to_customer.aclose()
        if self._lkapi:
            await self._lkapi.aclose()
        logger.info("TranslationManager closed")
