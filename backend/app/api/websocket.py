"""
WebSocket API endpoint.
"""

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query
from app.services.websocket_gateway import connection_manager
from app.api.rest import get_call_context


router = APIRouter()


@router.websocket("/calls/{call_id}/stream")
async def websocket_endpoint(websocket: WebSocket, call_id: str, token: str = Query(None)):
    """
    WebSocket endpoint for real-time call streaming.

    Streams:
    - Live transcripts
    - AI-generated insights
    - Sentiment updates
    - Data surface events
    - Disposition prefill

    Client can send:
    - refresh_insights
    - dismiss_insight
    - accept_suggestion
    - resync
    """

    # TODO: Authenticate JWT token
    # user = authenticate_jwt(token)
    # if not user:
    #     await websocket.close(code=1008)
    #     return

    # Connect client
    await connection_manager.connect(call_id, websocket)

    try:
        # Cache customer profile so insights worker has context
        await get_call_context(call_id)

        # Start streaming from Redis
        await connection_manager.start_streaming(call_id)

        # Handle client messages
        while True:
            data = await websocket.receive_json()
            await connection_manager.handle_client_message(call_id, data)

    except WebSocketDisconnect:
        print(f"Client disconnected: {call_id}")
        await connection_manager.disconnect(call_id)

    except Exception as e:
        print(f"WebSocket error for {call_id}: {e}")
        await connection_manager.disconnect(call_id)
