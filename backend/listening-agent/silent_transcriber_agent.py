import asyncio
import datetime
import json
import logging
import os

import aiohttp
from dotenv import load_dotenv
from livekit import api, rtc
from livekit.agents import (
    AgentServer,
    JobContext,
    JobProcess,
    cli,
    inference,
    AutoSubscribe,
)
from livekit.agents.stt import SpeechEventType
from livekit.plugins import silero

load_dotenv(".env")

logger = logging.getLogger("silent-transcriber")
logging.basicConfig(level=logging.INFO)

server = AgentServer()

BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8080")

# Global aiohttp session (created lazily)
_http_session: aiohttp.ClientSession | None = None


async def get_http_session() -> aiohttp.ClientSession:
    global _http_session
    if _http_session is None or _http_session.closed:
        _http_session = aiohttp.ClientSession()
    return _http_session


async def get_exotel_callsid(room_name: str) -> str | None:
    """Get the Exotel Call SID from SIP participant attributes via LiveKit API.
    Also logs ALL SIP headers for debugging.
    """
    try:
        lk_api = api.LiveKitAPI(
            url=os.getenv("LIVEKIT_URL", ""),
            api_key=os.getenv("LIVEKIT_API_KEY", ""),
            api_secret=os.getenv("LIVEKIT_API_SECRET", ""),
        )

        participants = await lk_api.room.list_participants(
            api.ListParticipantsRequest(room=room_name)
        )

        call_sid = None
        for p in participants.participants:
            attrs = dict(p.attributes) if p.attributes else {}
            logger.info(f"API Participant: {p.identity} | attributes={attrs}")

            # Log ALL SIP headers for debugging
            sip_headers = {k: v for k, v in attrs.items() if k.startswith("sip.")}
            if sip_headers:
                logger.info(f"=== SIP HEADERS for {p.identity} ===")
                for key, value in sorted(sip_headers.items()):
                    logger.info(f"  {key} = {value}")
                logger.info(f"=== END SIP HEADERS ===")

            if not call_sid and attrs:
                sid = attrs.get("sip.h.x-exotel-callsid")
                if sid:
                    call_sid = sid
                    logger.info(f"Exotel Call SID found: {call_sid} | participant={p.identity}")

        if not call_sid:
            logger.warning(f"No Exotel Call SID found in any participant | room={room_name}")
        return call_sid
    except Exception as e:
        logger.error(f"Failed to get Exotel Call SID via API: {e}")
        return None


async def push_transcript(call_sid: str, speaker: str, text: str, timestamp: str):
    """POST a transcript turn to the Spring Boot backend."""
    try:
        session = await get_http_session()
        payload = {
            "callSid": call_sid,
            "speaker": speaker,
            "text": text,
            "timestamp": timestamp,
        }
        async with session.post(
            f"{BACKEND_URL}/uwapi/transcript/push",
            json=payload,
            timeout=aiohttp.ClientTimeout(total=5),
        ) as resp:
            if resp.status != 200:
                logger.warning(f"Backend returned {resp.status}: {await resp.text()}")
            else:
                logger.info(f"Transcript pushed | callSid={call_sid} speaker={speaker}")
    except Exception as e:
        logger.error(f"Failed to push transcript: {e}")


async def push_meet_url(call_sid: str, meet_url: str):
    """POST the LiveKit Meet URL to the Spring Boot backend using callSid."""
    try:
        session = await get_http_session()
        payload = {
            "callSid": call_sid,
            "meetUrl": meet_url,
        }
        async with session.post(
            f"{BACKEND_URL}/uwapi/call/meet-url",
            json=payload,
            timeout=aiohttp.ClientTimeout(total=5),
        ) as resp:
            if resp.status != 200:
                logger.warning(f"Backend returned {resp.status} for meet-url: {await resp.text()}")
            else:
                logger.info(f"Meet URL pushed to backend | callSid={call_sid}")
    except Exception as e:
        logger.error(f"Failed to push meet URL: {e}")


def prewarm(proc: JobProcess):
    proc.userdata["vad"] = silero.VAD.load()
    logger.info("VAD model prewarmed successfully.")


server.setup_fnc = prewarm


def create_meet_token(room_name: str, user_id: str) -> str:
    token = api.AccessToken(
        os.getenv("LIVEKIT_API_KEY"),
        os.getenv("LIVEKIT_API_SECRET"),
    )

    token.with_identity(user_id)
    token.with_grants(
        api.VideoGrants(
            room_join=True,
            room=room_name,
            can_publish=True,
            can_subscribe=True,
        )
    )

    return token.to_jwt()


async def transcribe_sip_participant(
    track: rtc.RemoteAudioTrack, participant_id: str, stt: inference.STT, call_sid: str
):
    """Transcribe audio from the SIP (customer) participant."""
    logger.info(f"[SIP] Starting transcription | participant={participant_id} | callSid={call_sid}")

    # SIP audio arrives at 8kHz (G.711 telephony). Resample to 16kHz for optimal STT.
    audio_stream = rtc.AudioStream(track, sample_rate=16000, num_channels=1)
    stt_stream = stt.stream()
    logger.info(f"[SIP] Audio stream initialized (resampling to 16kHz) | participant={participant_id}")

    async def read_audio():
        frame_count = 0
        async for event in audio_stream:
            if frame_count == 0:
                logger.info(
                    f"[SIP] First frame | participant={participant_id} "
                    f"| sample_rate={event.frame.sample_rate} "
                    f"| channels={event.frame.num_channels} "
                    f"| samples={event.frame.samples_per_channel}"
                )
            stt_stream.push_frame(event.frame)
            frame_count += 1
        logger.info(f"[SIP] Audio stream ended | participant={participant_id} | total_frames={frame_count}")

    async def read_transcripts():
        transcript_count = 0
        async for event in stt_stream:
            if event.type == SpeechEventType.FINAL_TRANSCRIPT:
                text = event.alternatives[0].text
                if text.strip():
                    transcript_count += 1
                    timestamp = datetime.datetime.now().strftime("%H:%M:%S")
                    logger.info(f"[SIP] [{timestamp}] {participant_id}: {text}")
                    await push_transcript(call_sid, "customer", text, timestamp)
        logger.info(f"[SIP] Transcription stream ended | participant={participant_id} | total_transcripts={transcript_count}")

    try:
        await asyncio.gather(read_audio(), read_transcripts())
    except Exception as e:
        logger.error(f"[SIP] Transcription error | participant={participant_id} | error={e}")


async def transcribe_human_agent(
    track: rtc.RemoteAudioTrack, participant_id: str, stt: inference.STT, call_sid: str
):
    """Transcribe audio from the human agent participant."""
    logger.info(f"[HUMAN] Starting transcription | participant={participant_id} | callSid={call_sid}")

    audio_stream = rtc.AudioStream(track)
    stt_stream = stt.stream()
    logger.info(f"[HUMAN] Audio stream and STT stream initialized | participant={participant_id}")

    async def read_audio():
        frame_count = 0
        async for event in audio_stream:
            stt_stream.push_frame(event.frame)
            frame_count += 1
            if frame_count == 1:
                logger.info(f"[HUMAN] Receiving audio frames | participant={participant_id}")
        logger.info(f"[HUMAN] Audio stream ended | participant={participant_id} | total_frames={frame_count}")

    async def read_transcripts():
        transcript_count = 0
        async for event in stt_stream:
            if event.type == SpeechEventType.FINAL_TRANSCRIPT:
                text = event.alternatives[0].text
                if text.strip():
                    transcript_count += 1
                    timestamp = datetime.datetime.now().strftime("%H:%M:%S")
                    logger.info(f"[HUMAN] [{timestamp}] {participant_id}: {text}")
                    await push_transcript(call_sid, "agent", text, timestamp)
        logger.info(f"[HUMAN] Transcription stream ended | participant={participant_id} | total_transcripts={transcript_count}")

    try:
        await asyncio.gather(read_audio(), read_transcripts())
    except Exception as e:
        logger.error(f"[HUMAN] Transcription error | participant={participant_id} | error={e}")


@server.rtc_session(agent_name="silent-transcriber")
async def entrypoint(ctx: JobContext):
    room_name = ctx.room.name
    logger.info(f"Job received | room={room_name}")

    await ctx.connect(auto_subscribe=AutoSubscribe.SUBSCRIBE_ALL)
    logger.info(f"Connected to room | room={room_name}")

    # Extract Exotel Call SID from SIP participant attributes via LiveKit API
    call_sid = await get_exotel_callsid(room_name)
    if not call_sid:
        logger.error(f"Could not extract Exotel Call SID from room | room={room_name}")
        return
    logger.info(f"Exotel Call SID extracted: {call_sid} | room={room_name}")

    livekit_url = os.getenv("LIVEKIT_URL", "")
    token = create_meet_token(room_name, "human-agent")
    meet_url = f"https://meet.livekit.io/custom?liveKitUrl={livekit_url}&token={token}"

    logger.info(f"LiveKit Meet URL: {meet_url}")

    # Push Meet URL to the Spring Boot backend (identified by callSid)
    await push_meet_url(call_sid, meet_url)

    # Separate STT configs: SIP telephony audio needs longer endpointing
    stt_sip = inference.STT(
        model="deepgram/nova-3",
        language="multi",
        extra_kwargs={"endpointing": 100, "interim_results": True, "encoding": "linear16", "sample_rate": 16000},
    )
    stt_agent = inference.STT(
        model="deepgram/nova-3",
        language="multi",
        extra_kwargs={"endpointing": 25, "interim_results": True},
    )
    logger.info("STT engines initialized | sip_endpointing=100ms | agent_endpointing=25ms")

    @ctx.room.on("track_subscribed")
    def on_track_subscribed(track, publication, participant):
        if track.kind != rtc.TrackKind.KIND_AUDIO:
            return

        logger.info(f"Audio track subscribed | participant={participant.identity} | track_sid={track.sid}")

        if participant.identity.startswith("sip_"):
            asyncio.create_task(
                transcribe_sip_participant(track, participant.identity, stt_sip, call_sid)
            )
        else:
            asyncio.create_task(
                transcribe_human_agent(track, participant.identity, stt_agent, call_sid)
            )

    @ctx.room.on("track_unsubscribed")
    def on_track_unsubscribed(track, publication, participant):
        logger.info(f"Track unsubscribed | participant={participant.identity} | track_sid={track.sid}")

    # Handle tracks that were already subscribed BEFORE the listener was registered
    # (SIP participant is usually already in the room when the agent connects)
    for participant in ctx.room.remote_participants.values():
        for publication in participant.track_publications.values():
            if publication.track and publication.track.kind == rtc.TrackKind.KIND_AUDIO:
                logger.info(f"Found existing audio track | participant={participant.identity} | track_sid={publication.track.sid}")
                if participant.identity.startswith("sip_"):
                    asyncio.create_task(
                        transcribe_sip_participant(publication.track, participant.identity, stt_sip, call_sid)
                    )
                else:
                    asyncio.create_task(
                        transcribe_human_agent(publication.track, participant.identity, stt_agent, call_sid)
                    )

    @ctx.room.on("participant_connected")
    def on_participant_connected(participant):
        logger.info(f"Participant connected | identity={participant.identity}")
        if participant.identity == "human-agent":
            asyncio.create_task(publish_silent_track(ctx, room_name))

    async def publish_silent_track(job_ctx: JobContext, rn: str):
        """Publish a silent audio track so SIP answers the call when human agent joins."""
        silent_source = rtc.AudioSource(sample_rate=24000, num_channels=1)
        silent_track = rtc.LocalAudioTrack.create_audio_track("silent", silent_source)
        await job_ctx.room.local_participant.publish_track(silent_track)
        logger.info(f"Silent audio track published (human agent joined) | room={rn}")

    @ctx.room.on("participant_disconnected")
    def on_participant_disconnected(participant):
        logger.info(f"Participant disconnected | identity={participant.identity}")

    logger.info(f"Silent multi-speaker transcriber ready | room={room_name} | callSid={call_sid}")


def main():
    cli.run_app(server)


if __name__ == "__main__":
    main()
