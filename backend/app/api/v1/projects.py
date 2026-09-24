import logging
from typing import List, Optional
from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc, delete

from app.database import get_db, get_async_session
from app.models.project import Project, VideoChunk
from app.models.subtitle import SubtitleCue
from app.models.speaker import SpeakerProfile
from app.models.glossary import GlossaryTerm
from app.schemas.project import ProjectCreate, ProjectUpdate, ProjectResponse, ProjectListResponse
from app.services.storage_service import storage_service
from app.services.workflow_engine import workflow_engine
from app.services.video_downloader import video_downloader
from app.services.ws_manager import ws_manager
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/projects", tags=["Projects"])


class URLInfoRequest(BaseModel):
    url: str = Field(..., description="Video URL from Bilibili, Douyin, YouTube, etc.")


class ProjectFromURLCreate(BaseModel):
    url: str = Field(..., description="Video link (e.g. https://www.bilibili.com/video/BV...)")
    title: Optional[str] = None
    source_language: str = "zh"
    target_language: str = "vi"
    auto_start_pipeline: bool = True
    settings_override: Optional[dict] = None


@router.get("", response_model=ProjectListResponse)
async def list_projects(
    skip: int = 0,
    limit: int = 50,
    status: Optional[str] = None,
    search: Optional[str] = None,
    db: AsyncSession = Depends(get_db)
):
    """Retrieve all video translation projects with optional filtering."""
    stmt = select(Project).order_by(desc(Project.created_at))
    if status:
        stmt = stmt.where(Project.status == status)
    if search:
        stmt = stmt.where(Project.title.ilike(f"%{search}%"))

    stmt = stmt.offset(skip).limit(limit)
    res = await db.execute(stmt)
    projects = res.scalars().all()

    total_stmt = select(func.count(Project.id))
    if status:
        total_stmt = total_stmt.where(Project.status == status)
    if search:
        total_stmt = total_stmt.where(Project.title.ilike(f"%{search}%"))
    total_res = await db.execute(total_stmt)
    total = total_res.scalar() or 0

    items = []
    for p in projects:
        c_count_res = await db.execute(select(func.count(SubtitleCue.id)).where(SubtitleCue.project_id == p.id))
        s_count_res = await db.execute(select(func.count(SpeakerProfile.id)).where(SpeakerProfile.project_id == p.id))
        g_count_res = await db.execute(select(func.count(GlossaryTerm.id)).where(GlossaryTerm.project_id == p.id))

        resp = ProjectResponse.model_validate(p)
        resp.cue_count = c_count_res.scalar() or 0
        resp.speaker_count = s_count_res.scalar() or 0
        resp.glossary_count = g_count_res.scalar() or 0
        items.append(resp)

    return ProjectListResponse(total=total, items=items)


@router.post("", response_model=ProjectResponse, status_code=201)
async def create_project(
    data: ProjectCreate,
    db: AsyncSession = Depends(get_db)
):
    """Create a new project container."""
    project = Project(
        title=data.title,
        description=data.description,
        source_language=data.source_language,
        target_language=data.target_language,
        settings_override=data.settings_override
    )
    db.add(project)
    await db.commit()
    await db.refresh(project)
    resp = ProjectResponse.model_validate(project)
    resp.cue_count = 0
    resp.speaker_count = 0
    resp.glossary_count = 0
    return resp


@router.post("/url-info")
async def inspect_url_info(data: URLInfoRequest):
    """Inspect video URL (Bilibili, Douyin, YouTube) and return metadata without downloading."""
    return await video_downloader.extract_info(data.url)


@router.post("/from-url", response_model=ProjectResponse, status_code=201)
async def create_project_from_url(
    data: ProjectFromURLCreate,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db)
):
    """
    Creates a new project and downloads the video directly from Bilibili, Douyin, or YouTube URL,
    then automatically triggers the full translation pipeline.
    """
    initial_title = data.title or "Bilibili Video"
    project = Project(
        title=initial_title,
        original_video_url=data.url,
        source_language=data.source_language,
        target_language=data.target_language,
        settings_override=data.settings_override,
        status="INGESTING",
        current_stage="DOWNLOADING_URL",
        progress_percentage=5
    )
    db.add(project)
    await db.commit()
    await db.refresh(project)

    async def download_and_run_pipeline(project_id: str, url: str, auto_start: bool):
        async with get_async_session() as bg_db:
            res = await bg_db.execute(select(Project).where(Project.id == project_id))
            p = res.scalar_one_or_none()
            if not p:
                return

            try:
                await ws_manager.broadcast_to_project(project_id, {
                    "event": "stage_changed",
                    "stage": "DOWNLOADING_URL",
                    "progress": 5,
                    "message": "Đang kết nối và tải video từ Bilibili..."
                })

                last_db_time = 0.0
                last_db_pct = -1

                async def dl_progress(info: dict):
                    nonlocal last_db_time, last_db_pct
                    pct = info["pct"]
                    int_pct = min(100, max(0, int(pct)))
                    speed = info.get("speed") or ""
                    eta = info.get("eta") or ""

                    msg_parts = [f"Đang tải video ({pct}%)"]
                    if speed:
                        msg_parts.append(f"Tốc độ: {speed}")
                    if eta:
                        msg_parts.append(f"Còn: {eta}")
                    full_msg = " • ".join(msg_parts)

                    # 1. Real-time WebSocket broadcast
                    await ws_manager.broadcast_to_project(project_id, {
                        "event": "progress_update",
                        "stage": "DOWNLOADING_URL",
                        "progress": int_pct,
                        "percentage": int_pct,
                        "message": full_msg,
                        "speed": speed,
                        "eta": eta,
                    })

                    # 2. Update DB throttled every 1.5s or on each 1% change
                    now = asyncio.get_event_loop().time()
                    if (now - last_db_time >= 1.5) or (int_pct - last_db_pct >= 1) or int_pct >= 99:
                        last_db_time = now
                        last_db_pct = int_pct
                        p.progress_percentage = int_pct
                        p.current_stage = "DOWNLOADING_URL"
                        p.error_message = full_msg
                        await bg_db.commit()

                upload_dir = storage_service.get_project_dir(project_id)
                dl_result = await video_downloader.download_video(url, upload_dir, dl_progress)

                p.local_video_path = str(dl_result["file_path"])
                p.original_video_url = storage_service.get_relative_url(dl_result["file_path"])
                if dl_result.get("title") and (p.title == "Bilibili Video" or not p.title):
                    p.title = dl_result["title"]
                if dl_result.get("duration"):
                    p.video_duration_seconds = dl_result["duration"]

                p.current_stage = "INGESTED"
                p.progress_percentage = 100
                p.error_message = None
                await bg_db.commit()

                await ws_manager.broadcast_to_project(project_id, {
                    "event": "stage_changed",
                    "stage": "INGESTED",
                    "progress": 100,
                    "message": "Tải video Bilibili hoàn tất! Bắt đầu trích xuất âm thanh và nhận diện lời thoại..."
                })

                if auto_start:
                    await workflow_engine.run_pipeline(bg_db, project_id)

            except Exception as e:
                logger.error(f"Download & pipeline error for {project_id}: {e}", exc_info=True)
                p.status = "FAILED"
                p.error_message = f"Lỗi tải video Bilibili: {str(e)}"
                await bg_db.commit()
                await ws_manager.broadcast_to_project(project_id, {
                    "event": "pipeline_failed",
                    "status": "FAILED",
                    "error": str(e)
                })

    background_tasks.add_task(download_and_run_pipeline, project.id, data.url, data.auto_start_pipeline)
    resp = ProjectResponse.model_validate(project)
    resp.cue_count = 0
    resp.speaker_count = 0
    resp.glossary_count = 0
    return resp


@router.post("/{project_id}/upload", response_model=ProjectResponse)
async def upload_video_and_start(
    project_id: str,
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    auto_start_pipeline: bool = Form(True),
    db: AsyncSession = Depends(get_db)
):
    """Uploads video file directly to the project and optionally triggers the pipeline."""
    res = await db.execute(select(Project).where(Project.id == project_id))
    project = res.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    content = await file.read()
    saved_path = await storage_service.save_upload_file(project_id, file.filename or "video.mp4", content)

    project.local_video_path = str(saved_path)
    project.original_video_url = storage_service.get_relative_url(saved_path)
    project.status = "INGESTING" if auto_start_pipeline else "CREATED"
    await db.commit()
    await db.refresh(project)

    if auto_start_pipeline:
        async def run_bg_pipeline(pid: str):
            async with get_async_session() as bg_db:
                await workflow_engine.run_pipeline(bg_db, pid)

        background_tasks.add_task(run_bg_pipeline, project_id)

    resp = ProjectResponse.model_validate(project)
    resp.cue_count = (await db.execute(select(func.count(SubtitleCue.id)).where(SubtitleCue.project_id == project_id))).scalar() or 0
    resp.speaker_count = (await db.execute(select(func.count(SpeakerProfile.id)).where(SpeakerProfile.project_id == project_id))).scalar() or 0
    resp.glossary_count = (await db.execute(select(func.count(GlossaryTerm.id)).where(GlossaryTerm.project_id == project_id))).scalar() or 0
    return resp


@router.get("/{project_id}", response_model=ProjectResponse)
async def get_project(
    project_id: str,
    db: AsyncSession = Depends(get_db)
):
    """Get project details."""
    res = await db.execute(select(Project).where(Project.id == project_id))
    project = res.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    c_count = (await db.execute(select(func.count(SubtitleCue.id)).where(SubtitleCue.project_id == project_id))).scalar() or 0
    s_count = (await db.execute(select(func.count(SpeakerProfile.id)).where(SpeakerProfile.project_id == project_id))).scalar() or 0
    g_count = (await db.execute(select(func.count(GlossaryTerm.id)).where(GlossaryTerm.project_id == project_id))).scalar() or 0

    resp = ProjectResponse.model_validate(project)
    resp.cue_count = c_count
    resp.speaker_count = s_count
    resp.glossary_count = g_count
    return resp


@router.patch("/{project_id}", response_model=ProjectResponse)
async def update_project(
    project_id: str,
    data: ProjectUpdate,
    db: AsyncSession = Depends(get_db)
):
    """Update project metadata or settings."""
    res = await db.execute(select(Project).where(Project.id == project_id))
    project = res.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    update_dict = data.model_dump(exclude_unset=True)
    for k, v in update_dict.items():
        setattr(project, k, v)

    await db.commit()
    await db.refresh(project)

    resp = ProjectResponse.model_validate(project)
    resp.cue_count = (await db.execute(select(func.count(SubtitleCue.id)).where(SubtitleCue.project_id == project_id))).scalar() or 0
    resp.speaker_count = (await db.execute(select(func.count(SpeakerProfile.id)).where(SpeakerProfile.project_id == project_id))).scalar() or 0
    resp.glossary_count = (await db.execute(select(func.count(GlossaryTerm.id)).where(GlossaryTerm.project_id == project_id))).scalar() or 0
    return resp


@router.delete("/{project_id}")
async def delete_project(
    project_id: str,
    db: AsyncSession = Depends(get_db)
):
    """Delete project and associated files."""
    res = await db.execute(select(Project).where(Project.id == project_id))
    project = res.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    await db.delete(project)
    await db.commit()
    return {"success": True, "message": f"Project {project_id} deleted"}


@router.post("/{project_id}/dub")
async def trigger_project_dubbing(
    project_id: str,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db)
):
    """Trigger AI Dubbing for project subtitles."""
    from app.api.v1.tts import ProjectDubRequest, _run_dubbing_task
    res = await db.execute(select(Project).where(Project.id == project_id))
    project = res.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    voice = project.default_voice or "nova"
    background_tasks.add_task(
        _run_dubbing_task,
        project_id=project_id,
        voice=voice,
        model="tts-1",
        speed=1.0,
        ducking_volume=0.18,
        mix_original=True,
        speaker_voice_map={}
    )

    return {
        "success": True,
        "message": f"AI Dubbing started with voice '{voice}'",
        "project_id": project_id,
        "status": "DUBBING"
    }


@router.get("/{project_id}/dub")
async def get_project_dub_status(
    project_id: str,
    db: AsyncSession = Depends(get_db)
):
    """Get project dubbing status and media URLs."""
    res = await db.execute(select(Project).where(Project.id == project_id))
    project = res.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    return {
        "project_id": project.id,
        "status": project.status,
        "current_stage": project.current_stage,
        "progress_percentage": project.progress_percentage,
        "default_voice": project.default_voice,
        "dubbed_audio_url": project.dubbed_audio_url,
        "dubbed_video_url": project.dubbed_video_url
    }
