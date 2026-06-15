"""LiveKit Egress → S3 call recording for the browser (livekit) call mode.

Mirrors the pattern used in the voice-agent project: a single room-composite, audio-only
egress per call, uploaded straight to S3 by LiveKit Cloud egress. The public S3 URL is
computed up front (no polling) and reported to the backend so it can be forwarded to the
next-action service in place of the Exotel call recording.

Exotel calls are recorded by Exotel itself, so this is only used in browser mode.

Env is read lazily (inside the functions) so it works regardless of when load_dotenv() runs.
"""

import hashlib
import logging
import os
import time
from typing import Optional, Tuple

from livekit import api

logger = logging.getLogger("silent-transcriber.egress")


def _cfg() -> dict:
    """Read S3 + LiveKit config from the environment at call time (post load_dotenv)."""
    return {
        "lk_url": os.getenv("LIVEKIT_URL", ""),
        "lk_key": os.getenv("LIVEKIT_API_KEY", ""),
        "lk_secret": os.getenv("LIVEKIT_API_SECRET", ""),
        # Prefer egress-specific S3 keys; fall back to the AWS/Bedrock keys already in .env.
        "access_key": os.getenv("AWS_ACCESS_KEY") or os.getenv("AWS_ACCESS_KEY_ID", ""),
        "secret_key": os.getenv("AWS_SECRET_KEY") or os.getenv("AWS_SECRET_ACCESS_KEY", ""),
        "bucket": os.getenv("AWS_BUCKET_NAME") or os.getenv("S3_BUCKET", ""),
        "region": os.getenv("AWS_REGION", "ap-south-1"),
        "dest_path": os.getenv("DESTINATION_PATH", "").strip().lstrip("/").rstrip("/"),
        "base_url": os.getenv("BUCKET_FILE_PATH", "").strip().rstrip("/"),
        "enabled": os.getenv("LIVEKIT_EGRESS_ENABLED", "true").lower() == "true",
    }


def _is_configured(cfg: dict) -> bool:
    if not cfg["enabled"]:
        logger.info("[Egress] LIVEKIT_EGRESS_ENABLED=false — skipping recording")
        return False
    missing = [n for n, k in (("bucket", "bucket"), ("access key", "access_key"),
                              ("secret", "secret_key")) if not cfg[k]]
    if missing:
        logger.info("[Egress] not configured (%s missing) — skipping recording", ", ".join(missing))
        return False
    return True


def _file_type_and_codec():
    """Prefer MP3 when the installed livekit-api supports it, else fall back to OGG (opus)."""
    mp3 = getattr(api.EncodedFileType, "MP3", None)
    if mp3 is not None:
        advanced = api.EncodingOptions(
            audio_codec=api.AudioCodec.AC_MP3,
            audio_bitrate=128,
            audio_frequency=44100,
        )
        return mp3, "mp3", advanced
    return api.EncodedFileType.OGG, "ogg", None


def _build_filepath(room_name: str, ext: str, dest_path: str) -> str:
    epoch_ms = int(time.time() * 1000)
    room_hash = hashlib.md5(room_name.encode("utf-8")).hexdigest()
    suffix = f"VOICE_RECORDING/{epoch_ms}_{room_hash}_recording.{ext}"
    return f"{dest_path}/{suffix}" if dest_path else suffix


def _build_s3_url(filepath: str, cfg: dict) -> str:
    base = cfg["base_url"] or f"https://{cfg['bucket']}.s3.{cfg['region']}.amazonaws.com"
    return f"{base}/{filepath.lstrip('/')}"


async def start_audio_egress(room_name: str) -> Tuple[Optional[str], Optional[str]]:
    """Start an audio-only room-composite egress to S3.
    Returns (egress_id, public_s3_url); (None, None) if disabled/unconfigured or on error."""
    cfg = _cfg()
    if not _is_configured(cfg):
        return None, None

    file_type, ext, advanced = _file_type_and_codec()
    filepath = _build_filepath(room_name, ext, cfg["dest_path"])
    s3_url = _build_s3_url(filepath, cfg)

    file_output = api.EncodedFileOutput(
        file_type=file_type,
        filepath=filepath,
        s3=api.S3Upload(
            access_key=cfg["access_key"],
            secret=cfg["secret_key"],
            bucket=cfg["bucket"],
            region=cfg["region"],
        ),
    )
    req = api.RoomCompositeEgressRequest(
        room_name=room_name,
        audio_only=True,
        file_outputs=[file_output],
    )
    if advanced is not None:
        req.advanced.CopyFrom(advanced)

    try:
        async with api.LiveKitAPI(
            url=cfg["lk_url"], api_key=cfg["lk_key"], api_secret=cfg["lk_secret"]
        ) as lk:
            info = await lk.egress.start_room_composite_egress(req)
        logger.info(
            "[Egress] started | room=%s egress_id=%s url=%s", room_name, info.egress_id, s3_url
        )
        return info.egress_id, s3_url
    except Exception as e:
        logger.error("[Egress] failed to start | room=%s error=%s", room_name, e)
        return None, None


async def stop_egress(egress_id: Optional[str]) -> None:
    if not egress_id:
        return
    cfg = _cfg()
    try:
        async with api.LiveKitAPI(
            url=cfg["lk_url"], api_key=cfg["lk_key"], api_secret=cfg["lk_secret"]
        ) as lk:
            await lk.egress.stop_egress(api.StopEgressRequest(egress_id=egress_id))
        logger.info("[Egress] stopped | egress_id=%s", egress_id)
    except Exception as e:
        logger.error("[Egress] failed to stop | egress_id=%s error=%s", egress_id, e)
