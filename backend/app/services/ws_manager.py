import json
import logging
from typing import Dict, Set, Any
from fastapi import WebSocket

logger = logging.getLogger(__name__)


class ConnectionManager:
    """Manages active WebSocket connections grouped by project ID."""
    def __init__(self):
        # project_id -> Set of active WebSocket connections
        self.active_connections: Dict[str, Set[WebSocket]] = {}

    async def connect(self, websocket: WebSocket, project_id: str):
        await websocket.accept()
        if project_id not in self.active_connections:
            self.active_connections[project_id] = set()
        self.active_connections[project_id].add(websocket)
        logger.info(f"WebSocket client connected to project {project_id}. Total: {len(self.active_connections[project_id])}")

    def disconnect(self, websocket: WebSocket, project_id: str):
        if project_id in self.active_connections:
            self.active_connections[project_id].discard(websocket)
            if not self.active_connections[project_id]:
                del self.active_connections[project_id]
        logger.info(f"WebSocket client disconnected from project {project_id}")

    async def broadcast_to_project(self, project_id: str, event_type_or_data: Any, data: Any = None):
        """Broadcast a message to all connected clients for a project."""
        if project_id not in self.active_connections:
            return

        if data is None and isinstance(event_type_or_data, dict):
            event_type = event_type_or_data.get("event") or event_type_or_data.get("type") or "message"
            payload = event_type_or_data
        else:
            event_type = str(event_type_or_data)
            payload = data

        message = {
            "type": event_type,
            "project_id": project_id,
            "data": payload
        }
        raw_message = json.dumps(message, default=str)
        dead_sockets = set()

        for connection in list(self.active_connections.get(project_id, [])):
            try:
                await connection.send_text(raw_message)
            except Exception as e:
                logger.warning(f"Error sending to websocket: {e}")
                dead_sockets.add(connection)

        for dead in dead_sockets:
            self.disconnect(dead, project_id)


ws_manager = ConnectionManager()
