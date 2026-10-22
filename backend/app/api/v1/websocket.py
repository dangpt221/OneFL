import logging
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from app.services.ws_manager import ws_manager

logger = logging.getLogger(__name__)
router = APIRouter(tags=["WebSocket"])


@router.websocket("/ws/{project_id}")
async def project_websocket_endpoint(websocket: WebSocket, project_id: str):
    """WebSocket endpoint for real-time progress, log streaming, and cue synchronization."""
    import asyncio
    import json
    from app.database import get_async_session
    from app.models.project import Project
    from app.schemas.project import ProjectResponse
    from app.security import current_user
    async with get_async_session() as db:
        project = await db.get(Project, project_id)
        if not project or project.user_id != current_user.get():
            await websocket.close(code=4404)
            return
    await ws_manager.connect(websocket, project_id)
    async def snapshots():
        previous = None
        previous_stage = None
        while True:
            async with get_async_session() as db:
                project = await db.get(Project, project_id)
                if not project:
                    await websocket.close(code=4404)
                    return
                state = ProjectResponse.model_validate(project).model_dump(mode='json')
            current = json.dumps(state, sort_keys=True)
            if current != previous:
                stage = tuple(state[key] for key in ('status', 'current_stage', 'content_revision', 'active_job_id', 'original_video_url', 'burned_video_url', 'dubbed_audio_url', 'dubbed_video_url'))
                event = 'STATUS_UPDATE' if previous_stage != stage else 'PROGRESS_UPDATE'
                state.update(progress=state['progress_percentage'], message=state['error_message'])
                await asyncio.wait_for(websocket.send_json({'type': event, 'project_id': project_id, 'data': state}), 3)
                previous = current
                previous_stage = stage
            await asyncio.sleep(2)
    snapshot_task = asyncio.create_task(snapshots())
    receiver = None
    try:
        while True:
            receiver = asyncio.create_task(websocket.receive_text())
            done, pending = await asyncio.wait([receiver, snapshot_task], return_when=asyncio.FIRST_COMPLETED)
            if snapshot_task in done:
                receiver.cancel()
                await asyncio.gather(receiver, return_exceptions=True)
                await snapshot_task
                return
            if receiver.result() == 'ping':
                await asyncio.wait_for(websocket.send_text('pong'), 3)
    except WebSocketDisconnect:
        pass  # Normal client disconnect, cleaned up below.
    except Exception:
        logger.exception('WebSocket feed failed for %s', project_id)
    finally:
        snapshot_task.cancel()
        if receiver:
            receiver.cancel()
        await asyncio.gather(*[t for t in (snapshot_task, receiver) if t], return_exceptions=True)
        ws_manager.disconnect(websocket, project_id)
