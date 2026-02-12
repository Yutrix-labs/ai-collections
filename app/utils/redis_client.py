"""
Redis client utility with Streams support.
"""

import json
import redis.asyncio as redis
from typing import Optional, Dict, List, Any
from app.config import settings


class RedisClient:
    """Redis client wrapper with helper methods for Streams."""

    def __init__(self):
        self.client: Optional[redis.Redis] = None

    async def connect(self):
        """Connect to Redis."""
        self.client = await redis.from_url(
            settings.redis_url,
            encoding="utf-8",
            decode_responses=True
        )
        return self.client

    async def disconnect(self):
        """Disconnect from Redis."""
        if self.client:
            await self.client.close()

    async def xadd(self, stream_key: str, data: Dict[str, Any]) -> str:
        """Add message to stream."""
        # Convert dict values to strings for Redis
        redis_data = {k: json.dumps(v) if not isinstance(v, str) else v
                      for k, v in data.items()}
        return await self.client.xadd(stream_key, redis_data)

    async def xreadgroup(
        self,
        group: str,
        consumer: str,
        streams: Dict[str, str],
        count: int = 10,
        block: int = 1000
    ) -> List[tuple]:
        """Read from stream using consumer group."""
        result = await self.client.xreadgroup(
            groupname=group,
            consumername=consumer,
            streams=streams,
            count=count,
            block=block
        )
        return result

    async def xack(self, stream_key: str, group: str, msg_id: str):
        """Acknowledge message."""
        await self.client.xack(stream_key, group, msg_id)

    async def xgroup_create(
        self,
        stream_key: str,
        group: str,
        id: str = "0",
        mkstream: bool = True
    ):
        """Create consumer group."""
        try:
            await self.client.xgroup_create(
                stream_key, group, id=id, mkstream=mkstream
            )
        except redis.ResponseError as e:
            if "BUSYGROUP" not in str(e):
                raise

    async def set(self, key: str, value: Any, ex: Optional[int] = None):
        """Set key-value with optional expiration."""
        if not isinstance(value, str):
            value = json.dumps(value)
        await self.client.set(key, value, ex=ex)

    async def get(self, key: str) -> Optional[str]:
        """Get value by key."""
        return await self.client.get(key)

    async def get_json(self, key: str) -> Optional[Dict]:
        """Get JSON value by key."""
        value = await self.get(key)
        if value:
            return json.loads(value)
        return None

    async def delete(self, key: str):
        """Delete key."""
        await self.client.delete(key)

    async def sadd(self, key: str, *members):
        """Add members to set."""
        await self.client.sadd(key, *members)

    async def sismember(self, key: str, member: str) -> bool:
        """Check if member is in set."""
        return await self.client.sismember(key, member)

    async def expire(self, key: str, seconds: int):
        """Set expiration on key."""
        await self.client.expire(key, seconds)

    async def llen(self, key: str) -> int:
        """Get list length."""
        return await self.client.llen(key)

    async def rpush(self, key: str, *values):
        """Push to end of list."""
        await self.client.rpush(key, *values)

    async def lrange(self, key: str, start: int, end: int) -> List[str]:
        """Get range from list."""
        return await self.client.lrange(key, start, end)


# Helper functions for common Redis operations

def get_transcript_stream_key(call_id: str) -> str:
    """Get transcript stream key."""
    return f"call:{call_id}:transcript"


def get_insight_jobs_stream_key(call_id: str) -> str:
    """Get insight jobs stream key."""
    return f"call:{call_id}:insight_jobs"


def get_insights_stream_key(call_id: str) -> str:
    """Get insights stream key."""
    return f"call:{call_id}:insights"


def get_profile_key(call_id: str) -> str:
    """Get profile cache key."""
    return f"call:{call_id}:profile"


def get_sentiment_key(call_id: str) -> str:
    """Get sentiment state key."""
    return f"call:{call_id}:sentiment"


def get_topics_seen_key(call_id: str) -> str:
    """Get topics seen set key."""
    return f"call:{call_id}:topics_seen"


def get_last_sentiment_key(call_id: str) -> str:
    """Get last sentiment key."""
    return f"call:{call_id}:last_sentiment"


def get_rate_limit_key(call_id: str, insight_type: str) -> str:
    """Get rate limit key."""
    return f"call:{call_id}:last_{insight_type}_time"


# Global Redis client instance
redis_client = RedisClient()
