"""
Insights worker - consumes insight_jobs stream and generates insights via LLM.
"""

import asyncio
import json
from app.utils.redis_client import redis_client, get_insight_jobs_stream_key
from app.services.ai_insights_engine import generate_insights
from app.config import settings


async def get_active_calls():
    """
    Get list of active call IDs by scanning Redis for insight_jobs streams.
    """
    call_ids = set()
    cursor = 0
    while True:
        cursor, keys = await redis_client.client.scan(
            cursor=cursor, match="call:*:insight_jobs", count=100
        )
        for key in keys:
            # Extract call_id from "call:{call_id}:insight_jobs"
            parts = key.split(":")
            if len(parts) >= 3:
                call_ids.add(parts[1])
        if cursor == 0:
            break
    return list(call_ids)


async def ensure_consumer_group(stream_key: str, group: str):
    """Create consumer group for a stream if it doesn't exist."""
    try:
        await redis_client.xgroup_create(stream_key, group, id="0", mkstream=True)
    except Exception:
        pass  # Group already exists


async def insights_worker():
    """
    Long-running worker that consumes insight_jobs streams.
    """
    print("Starting insights worker...")

    # Connect to Redis
    await redis_client.connect()
    print("Connected to Redis")

    while True:
        try:
            # Get active calls that have insight_jobs streams
            active_calls = await get_active_calls()

            for call_id in active_calls:
                stream_key = get_insight_jobs_stream_key(call_id)

                # Ensure consumer group exists for this stream
                await ensure_consumer_group(stream_key, "insights-group")

                try:
                    # Read from stream (process one job at a time)
                    messages = await redis_client.xreadgroup(
                        group="insights-group",
                        consumer="worker-1",
                        streams={stream_key: ">"},
                        count=1,
                        block=100  # Short block so we cycle through calls quickly
                    )

                    if messages:
                        for stream, msg_list in messages:
                            for msg_id, data in msg_list:
                                # Parse job data
                                trigger = data.get('trigger', '')
                                transcript_window = json.loads(data.get('transcript_window', '[]'))

                                print(f"Generating insights for call {call_id}, trigger: {trigger}")

                                # Generate insights (calls LLM)
                                insights = await generate_insights(
                                    call_id,
                                    trigger,
                                    transcript_window
                                )

                                print(f"Generated {len(insights)} insights for call {call_id}")

                                # Acknowledge message
                                await redis_client.xack(stream_key, "insights-group", msg_id)

                except Exception as e:
                    print(f"Error processing insight job for {call_id}: {e}")

            # Sleep briefly
            await asyncio.sleep(settings.insights_worker_poll_interval)

        except KeyboardInterrupt:
            print("Insights worker shutting down...")
            break
        except Exception as e:
            print(f"Error in insights worker: {e}")
            await asyncio.sleep(1)

    # Cleanup
    await redis_client.disconnect()


if __name__ == "__main__":
    asyncio.run(insights_worker())
