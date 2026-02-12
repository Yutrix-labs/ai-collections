"""
WebSocket gateway service for real-time communication.
"""

import asyncio
import json
from datetime import datetime
from typing import Dict, Optional
from fastapi import WebSocket, WebSocketDisconnect
from app.utils.redis_client import (
    redis_client,
    get_transcript_stream_key,
    get_insights_stream_key
)


class ConnectionManager:
    """Manages WebSocket connections for active calls."""

    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}
        self.stream_tasks: Dict[str, list] = {}

    async def connect(self, call_id: str, websocket: WebSocket):
        """Accept and register a WebSocket connection."""
        await websocket.accept()
        self.active_connections[call_id] = websocket
        self.stream_tasks[call_id] = []

    async def disconnect(self, call_id: str):
        """Remove WebSocket connection and cancel stream tasks."""
        if call_id in self.active_connections:
            del self.active_connections[call_id]

        # Cancel all stream listening tasks
        if call_id in self.stream_tasks:
            for task in self.stream_tasks[call_id]:
                task.cancel()
            del self.stream_tasks[call_id]

    def is_connected(self, call_id: str) -> bool:
        """Check if call has active connection."""
        return call_id in self.active_connections

    async def send_event(self, call_id: str, event: dict):
        """Send event to connected client."""
        ws = self.active_connections.get(call_id)
        if ws:
            try:
                await ws.send_json(event)
            except Exception as e:
                print(f"Error sending event to {call_id}: {e}")
                await self.disconnect(call_id)

    async def broadcast_transcript(self, call_id: str, utterance: dict):
        """Send transcript event to client."""
        await self.send_event(call_id, {
            "event": "transcript",
            "timestamp": datetime.utcnow().isoformat(),
            "payload": utterance,
        })

    async def broadcast_insight(self, call_id: str, insight: dict):
        """Send insight event to client."""
        await self.send_event(call_id, {
            "event": "insight",
            "timestamp": datetime.utcnow().isoformat(),
            "payload": insight,
        })

    async def broadcast_sentiment_update(self, call_id: str, sentiment_data: dict):
        """Send sentiment update event to client."""
        await self.send_event(call_id, {
            "event": "sentiment_update",
            "timestamp": datetime.utcnow().isoformat(),
            "payload": sentiment_data,
        })

    async def broadcast_data_surface(self, call_id: str, data: dict):
        """Send data surface event to client."""
        await self.send_event(call_id, {
            "event": "data_surface",
            "timestamp": datetime.utcnow().isoformat(),
            "payload": data,
        })

    async def broadcast_disposition_prefill(self, call_id: str, disposition: dict):
        """Send disposition prefill event to client."""
        await self.send_event(call_id, {
            "event": "disposition_prefill",
            "timestamp": datetime.utcnow().isoformat(),
            "payload": disposition,
        })

    async def broadcast_call_status(self, call_id: str, status: str, duration_sec: Optional[int] = None):
        """Send call status event to client."""
        await self.send_event(call_id, {
            "event": "call_status",
            "timestamp": datetime.utcnow().isoformat(),
            "payload": {
                "status": status,
                "duration_sec": duration_sec,
            },
        })

    async def listen_to_transcript_stream(self, call_id: str):
        """Listen to transcript Redis stream and broadcast to client."""
        stream_key = get_transcript_stream_key(call_id)
        last_id = "0"

        while self.is_connected(call_id):
            try:
                # Read from stream
                messages = await redis_client.client.xread(
                    {stream_key: last_id},
                    count=10,
                    block=1000
                )

                if messages:
                    for stream, msg_list in messages:
                        for msg_id, data in msg_list:
                            last_id = msg_id
                            # Parse JSON data from Redis
                            utterance = {k: json.loads(v) if v.startswith('{') or v.startswith('[') else v
                                       for k, v in data.items()}
                            await self.broadcast_transcript(call_id, utterance)

            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"Error in transcript stream for {call_id}: {e}")
                await asyncio.sleep(1)

    async def listen_to_insights_stream(self, call_id: str):
        """Listen to insights Redis stream and broadcast to client."""
        stream_key = get_insights_stream_key(call_id)
        last_id = "0"

        while self.is_connected(call_id):
            try:
                # Read from stream
                messages = await redis_client.client.xread(
                    {stream_key: last_id},
                    count=10,
                    block=1000
                )

                if messages:
                    for stream, msg_list in messages:
                        for msg_id, data in msg_list:
                            last_id = msg_id
                            # Parse JSON data from Redis
                            insight = {k: json.loads(v) if v.startswith('{') or v.startswith('[') else v
                                     for k, v in data.items()}
                            await self.broadcast_insight(call_id, insight)

            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"Error in insights stream for {call_id}: {e}")
                await asyncio.sleep(1)

    async def start_streaming(self, call_id: str):
        """Start listening to all Redis streams for this call."""
        # Create tasks for each stream
        transcript_task = asyncio.create_task(self.listen_to_transcript_stream(call_id))
        insights_task = asyncio.create_task(self.listen_to_insights_stream(call_id))

        # Store tasks so they can be cancelled on disconnect
        self.stream_tasks[call_id] = [transcript_task, insights_task]

    async def handle_client_message(self, call_id: str, message: dict):
        """Handle messages from client."""
        action = message.get("action")

        if action == "refresh_insights":
            # Trigger insight generation
            from app.services.ai_insights_engine import trigger_insight_generation
            await trigger_insight_generation(call_id, trigger="agent_refresh")

        elif action == "dismiss_insight":
            insight_id = message.get("insight_id")
            # Store dismissal (could update database or cache)
            print(f"Insight {insight_id} dismissed by agent")

        elif action == "accept_suggestion":
            insight_id = message.get("insight_id")
            # Store acceptance (could update database or cache)
            print(f"Insight {insight_id} accepted by agent")

        elif action == "resync":
            # Handle resync request (replay missed events)
            last_utterance_id = message.get("last_utterance_id", "0")
            last_insight_id = message.get("last_insight_id", "0")
            await self.resync_streams(call_id, last_utterance_id, last_insight_id)

    async def resync_streams(self, call_id: str, last_utterance_id: str, last_insight_id: str):
        """Replay missed events after reconnection."""
        # Fetch missed utterances
        transcript_stream = get_transcript_stream_key(call_id)
        messages = await redis_client.client.xread(
            {transcript_stream: last_utterance_id},
            count=100
        )

        if messages:
            for stream, msg_list in messages:
                for msg_id, data in msg_list:
                    utterance = {k: json.loads(v) if v.startswith('{') or v.startswith('[') else v
                               for k, v in data.items()}
                    await self.broadcast_transcript(call_id, utterance)

        # Fetch missed insights
        insights_stream = get_insights_stream_key(call_id)
        messages = await redis_client.client.xread(
            {insights_stream: last_insight_id},
            count=100
        )

        if messages:
            for stream, msg_list in messages:
                for msg_id, data in msg_list:
                    insight = {k: json.loads(v) if v.startswith('{') or v.startswith('[') else v
                             for k, v in data.items()}
                    await self.broadcast_insight(call_id, insight)


# Global connection manager instance
connection_manager = ConnectionManager()
