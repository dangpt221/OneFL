import logging
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from app.services.ws_manager import ws_manager

logger = logging.getLogger(__name__)
router = APIRouter(tags=["WebSocket"])


@router.websocket("/ws/{project_id}")
async def project_websocket_endpoint(websocket: WebSocket, project_id: str):
    """WebSocket endpoint for real-time progress, log streaming, and cue synchronization."""
    await ws_manager.connect(websocket, project_id)
    try:
        # Send initial welcome / handshake
        await websocket.send_json({
            "type": "CONNECTION_ESTABLISHED",
            "project_id": project_id,
            "message": f"Connected to live feed for project {project_id}"
        })

        while True:
            # Keep connection alive and listen for client actions (ping, request sync)
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_text("pong")
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket, project_id)
    except Exception as e:
        logger.warning(f"WebSocket exception on project {project_id}: {e}")
        ws_manager.disconnect(websocket, project_id)
