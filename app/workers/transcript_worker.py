"""
Transcript worker - consumes transcript stream and processes utterances.
"""

import asyncio
import json
from app.utils.redis_client import redis_client, get_transcript_stream_key
from app.services.transcript_aggregator import process_utterance
from app.config import settings


async def get_active_calls():
    """
    Get list of active call IDs.
    In production, fetch from database or Redis set.
    """
    # For demo, return empty list (calls added dynamically)
    # In production: SELECT call_id FROM calls WHERE status = 'active'
    return []


async def transcript_worker():
    """
    Long-running worker that consumes transcript streams.
    """
    print("Starting transcript worker...")

    # Connect to Redis
    await redis_client.connect()

    # Create consumer group
    # Note: In production, create groups per call dynamically
    try:
        await redis_client.xgroup_create(
            "call:*:transcript",
            "aggregator-group",
            id="0",
            mkstream=True
        )
    except Exception as e:
        print(f"Consumer group may already exist: {e}")

    utterance_counts = {}

    while True:
        try:
            # Get active calls
            active_calls = await get_active_calls()

            # For demo, also check for any streams matching pattern
            # In production, use active_calls from database

            for call_id in active_calls:
                stream_key = get_transcript_stream_key(call_id)

                try:
                    # Read from stream
                    messages = await redis_client.xreadgroup(
                        group="aggregator-group",
                        consumer="worker-1",
                        streams={stream_key: ">"},
                        count=settings.stream_read_count,
                        block=settings.stream_block_ms
                    )

                    if messages:
                        for stream, msg_list in messages:
                            for msg_id, data in msg_list:
                                # Parse utterance
                                utterance = {
                                    k: json.loads(v) if v.startswith('{') or v.startswith('[') else v
                                    for k, v in data.items()
                                }

                                # Track utterance count
                                if call_id not in utterance_counts:
                                    utterance_counts[call_id] = 0
                                utterance_counts[call_id] += 1

                                # Process utterance
                                await process_utterance(
                                    call_id,
                                    utterance,
                                    utterance_counts[call_id]
                                )

                                # Acknowledge message
                                await redis_client.xack(stream, "aggregator-group", msg_id)

                except Exception as e:
                    print(f"Error processing transcript stream for {call_id}: {e}")

            # Sleep briefly
            await asyncio.sleep(settings.transcript_worker_poll_interval)

        except KeyboardInterrupt:
            print("Transcript worker shutting down...")
            break
        except Exception as e:
            print(f"Error in transcript worker: {e}")
            await asyncio.sleep(1)

    # Cleanup
    await redis_client.disconnect()


if __name__ == "__main__":
    asyncio.run(transcript_worker())
