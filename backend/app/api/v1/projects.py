import logging
import asyncio
from typing import List, Optional
from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc, delete, update

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
from app.services.job_service import job_service
from app.security import current_user
from app.services.artifact_service import invalidate_artifacts
from app.services.media_process import probe_media
from app.models.speaker import RelationshipMatrix
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
    if skip < 0 or not 1 <= limit <= 100:
        raise HTTPException(422, 'Invalid pagination')
    stmt = select(Project).where(Project.user_id == current_user.get()).order_by(desc(Project.created_at))
    if status:
        stmt = stmt.where(Project.status == status)
    if search:
        stmt = stmt.where(Project.title.ilike(f"%{search}%"))

    stmt = stmt.offset(skip).limit(limit)
    res = await db.execute(stmt)
    projects = res.scalars().all()

    total_stmt = select(func.count(Project.id)).where(Project.user_id == current_user.get())
    if status:
        total_stmt = total_stmt.where(Project.status == status)
    if search:
        total_stmt = total_stmt.where(Project.title.ilike(f"%{search}%"))
    total_res = await db.execute(total_stmt)
    total = total_res.scalar() or 0

    ids = [p.id for p in projects]
    counts = []
    for model in (SubtitleCue, SpeakerProfile, GlossaryTerm):
        rows = await db.execute(select(model.project_id, func.count(model.id)).where(model.project_id.in_(ids)).group_by(model.project_id))
        counts.append(dict(rows.all()))
    items = []
    for p in projects:
        resp = ProjectResponse.model_validate(p)
        resp.cue_count, resp.speaker_count, resp.glossary_count = (mapping.get(p.id, 0) for mapping in counts)
        items.append(resp)

    return ProjectListResponse(total=total, items=items)


@router.post("", response_model=ProjectResponse, status_code=201)
async def create_project(
    data: ProjectCreate,
    db: AsyncSession = Depends(get_db)
):
    """Create a new project container."""
    project = Project(
        user_id=current_user.get(),
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
        user_id=current_user.get(),
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

    await job_service.enqueue(db, project.id, 'DOWNLOAD', {'url': data.url, 'auto_start': data.auto_start_pipeline})
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
    await require_idle_project(db, project_id)
    saved_path = await storage_service.save_upload_file_stream(project_id, file)
    return await replace_project_source(db, project_id, saved_path, auto_start_pipeline)


class UploadSessionRequest(BaseModel):
    filename: str = Field(min_length=1, max_length=255)
    size: int = Field(gt=0)
    total_chunks: int = Field(gt=0, le=100000)


async def require_idle_project(db, project_id):
    project = await db.get(Project, project_id, populate_existing=True)
    if not project:
        raise HTTPException(404, 'Project not found')
    if project.active_job_id:
        raise HTTPException(409, 'Cancel the active job before changing project input')
    return project


@router.post('/{project_id}/uploads')
async def begin_project_upload(project_id: str, data: UploadSessionRequest, db: AsyncSession = Depends(get_db)):
    await require_idle_project(db, project_id)
    return await storage_service.begin_upload(project_id, data.filename, data.size, data.total_chunks)


@router.get('/{project_id}/uploads/{upload_id}')
async def get_upload_status(project_id: str, upload_id: str, db: AsyncSession = Depends(get_db)):
    if not await db.get(Project, project_id):
        raise HTTPException(404, 'Project not found')
    return await storage_service.upload_status(project_id, upload_id)


@router.post('/{project_id}/upload-chunk')
async def upload_video_chunk(
    project_id: str, upload_id: str = Form(...), chunk_index: int = Form(...),
    offset: int = Form(...), file: UploadFile = File(...), db: AsyncSession = Depends(get_db),
):
    await require_idle_project(db, project_id)
    await storage_service.receive_chunk(project_id, upload_id, chunk_index, offset, file)
    return {'success': True, 'chunk_index': chunk_index}


@router.post('/{project_id}/uploads/{upload_id}/finalize', response_model=ProjectResponse)
async def finalize_project_upload(project_id: str, upload_id: str, auto_start_pipeline: bool = True, db: AsyncSession = Depends(get_db)):
    path = await storage_service.finalize_upload(project_id, upload_id)
    return await replace_project_source(db, project_id, path, auto_start_pipeline)


async def replace_project_source(db, project_id: str, path: Path, auto_start: bool):
    async with storage_service._upload_lock(storage_service.get_project_dir(project_id)):
        return await _replace_project_source_locked(db, project_id, path, auto_start)


async def _replace_project_source_locked(db, project_id: str, path: Path, auto_start: bool):
    project = await db.get(Project, project_id, populate_existing=True)
    if not project:
        raise HTTPException(404, 'Project not found')
    # A repeated finalize must not enqueue the same input twice, even after its
    # first pipeline has completed. An explicitly new upload gets a new ID/path.
    if project.local_video_path == str(path):
        return ProjectResponse.model_validate(project)
    duration = await probe_media(path, require_video=True)
    claim = await db.execute(update(Project).where(Project.id == project_id, Project.active_job_id.is_(None)).values(current_stage='INGESTED'))
    if claim.rowcount != 1:
        await db.rollback()
        raise HTTPException(409, 'Cancel the active job before replacing project input')
    await db.refresh(project)
    await db.execute(delete(SubtitleCue).where(SubtitleCue.project_id == project_id))
    await db.execute(delete(RelationshipMatrix).where(RelationshipMatrix.project_id == project_id))
    await db.execute(delete(SpeakerProfile).where(SpeakerProfile.project_id == project_id))
    invalidate_artifacts(project, audio=True)
    project.extracted_audio_path = None
    project.subtitles_ass_path = project.subtitles_srt_path = None
    project.local_video_path, project.original_video_url = str(path), storage_service.get_relative_url(path)
    project.video_duration_seconds = duration
    project.status, project.current_stage, project.progress_percentage = 'CREATED', 'INGESTED', 0
    await db.commit()
    if auto_start:
        await job_service.enqueue(db, project_id, 'PIPELINE', {})
    await db.refresh(project)
    return ProjectResponse.model_validate(project)


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
    if any(key in update_dict and update_dict[key] != getattr(project, key) for key in ('source_language', 'target_language', 'settings_override', 'default_voice')):
        invalidate_artifacts(project, audio=True)
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

    await job_service.cancel(db, project_id)
    await db.refresh(project)
    await db.delete(project)
    await db.commit()
    await storage_service.delete_project_files(project_id)
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

    from app.api.v1.tts import start_project_dubbing
    return await start_project_dubbing(project_id, background_tasks, ProjectDubRequest(voice=project.default_voice or 'vi-VN-HoaiMyNeural'), db)


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


class ResetStatusRequest(BaseModel):
    target_status: str = Field('WAITING_REVIEW', pattern='^(CREATED|WAITING_REVIEW)$')


@router.post("/{project_id}/reset-status")
async def reset_project_status(
    project_id: str,
    data: "ResetStatusRequest",
    db: AsyncSession = Depends(get_db)
):
    """Resets stuck/interrupted project status back to WAITING_REVIEW."""
    res = await db.execute(select(Project).where(Project.id == project_id))
    project = res.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    await job_service.cancel(db, project_id)
    await db.refresh(project)
    target_status = data.target_status
    project.status = target_status or "WAITING_REVIEW"
    project.current_stage = target_status or "WAITING_REVIEW"
    project.error_message = "Đã đặt lại trạng thái dự án. Bạn có thể tiếp tục thao tác trên Studio."
    await db.commit()
    await db.refresh(project)

    await ws_manager.broadcast_to_project(project_id, "STATUS_UPDATE", {
        "status": project.status,
        "stage": project.current_stage,
        "current_stage": project.current_stage,
        "progress": project.progress_percentage,
        "message": project.error_message
    })

    return {
        "success": True,
        "message": f"Project status reset to {project.status}",
        "status": project.status
    }


@router.post("/{project_id}/resume-dubbing")
async def resume_project_dubbing(
    project_id: str,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db)
):
    """Resumes interrupted dubbing using existing cached clips on disk."""
    from app.api.v1.tts import _run_dubbing_task
    res = await db.execute(select(Project).where(Project.id == project_id))
    project = res.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    if not project.last_dub_config:
        raise HTTPException(409, 'No saved dubbing configuration to resume')
    from app.api.v1.tts import ProjectDubRequest, start_project_dubbing
    return await start_project_dubbing(project_id, background_tasks, ProjectDubRequest(**project.last_dub_config), db)


@router.get('/{project_id}/jobs/{job_id}')
async def get_project_job(project_id: str, job_id: str, db: AsyncSession = Depends(get_db)):
    from app.models.job import Job
    job = await db.get(Job, job_id)
    if not job or job.project_id != project_id:
        raise HTTPException(404, 'Job not found')
    return {'id': job.id, 'status': job.status, 'error': job.error, 'kind': job.kind, 'heartbeat_at': job.heartbeat_at, 'result': job.result}
