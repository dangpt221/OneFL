"""URL ingestion runs under the same durable job ownership as other stages."""
from pathlib import Path
import time
from app.models.project import Project
from app.services.media_process import probe_media
from app.services.storage_service import storage_service
from app.services.video_downloader import video_downloader
from app.services.ws_manager import ws_manager


async def download_project(db, project_id: str, url: str, auto_start: bool = True):
    project = await db.get(Project, project_id)
    if not project:
        raise ValueError('Project not found')
    project.status, project.current_stage = 'INGESTING', 'DOWNLOADING_URL'
    await db.commit()
    last_progress = 0.
    async def progress(info):
        nonlocal last_progress
        now = time.monotonic()
        if now - last_progress < 0.5 and info['pct'] < 100:
            return
        last_progress = now
        project.progress_percentage = min(99, int(info['pct']))
        project.error_message = f"Downloading video: {info['pct']}%"
        await db.commit()
        await ws_manager.broadcast_to_project(project_id, 'PROGRESS_UPDATE', {
            'stage': 'DOWNLOADING_URL', 'progress': project.progress_percentage,
            'message': project.error_message,
        })
    result = await video_downloader.download_video(url, storage_service.get_project_dir(project_id), progress)
    path = Path(result['file_path'])
    project.video_duration_seconds = await probe_media(path, require_video=True)
    project.local_video_path = str(path)
    project.original_video_url = storage_service.get_relative_url(path)
    if project.title == 'Bilibili Video':
        project.title = result['title']
    project.status, project.current_stage = 'CREATED', 'INGESTED'
    project.progress_percentage, project.error_message = 0, None
    await db.commit()
    if auto_start:
        from app.services.workflow_engine import workflow_engine
        await workflow_engine.run_pipeline(db, project_id)
    else:
        await ws_manager.broadcast_to_project(project_id, 'STATUS_UPDATE', {'status': 'CREATED', 'current_stage': 'INGESTED', 'progress': 0})
