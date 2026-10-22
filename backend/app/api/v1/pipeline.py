import logging
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import get_db, get_async_session
from app.models.project import Project
from typing import Optional
from app.schemas.translation import PipelineTriggerRequest, PipelineStatusResponse, BurnOptionsRequest
from app.services.workflow_engine import workflow_engine
from app.services.job_service import job_service

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/projects/{project_id}/pipeline", tags=["Pipeline & Processing"])


@router.post("/trigger")
async def trigger_pipeline(
    project_id: str,
    req: PipelineTriggerRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db)
):
    """Trigger pipeline execution from a specified stage."""
    res = await db.execute(select(Project).where(Project.id == project_id))
    project = res.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    job = await job_service.enqueue(db, project_id, 'PIPELINE', {'start_stage': req.stage, 'force_reprocess': req.force_reprocess})
    return {"success": True, "job_id": job.id, "message": "Pipeline queued"}


@router.post("/burn")
async def start_burning(
    project_id: str,
    background_tasks: BackgroundTasks,
    req: Optional[BurnOptionsRequest] = None,
    db: AsyncSession = Depends(get_db)
):
    """Start burning subtitles onto the video with optional custom presets and bilingual mode."""
    res = await db.execute(select(Project).where(Project.id == project_id))
    project = res.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    updates = {}
    if req:
        existing_cfg = dict(project.settings_override or {})
        existing_cfg.update(req.model_dump(exclude_unset=True))
        updates['settings_override'] = existing_cfg

    job = await job_service.enqueue(db, project_id, 'BURN', {}, project_updates=updates)
    return {"success": True, "job_id": job.id, "message": "Video burning queued"}


@router.get("/status", response_model=PipelineStatusResponse)
async def get_pipeline_status(
    project_id: str,
    db: AsyncSession = Depends(get_db)
):
    """Get current pipeline progress and active stage."""
    res = await db.execute(select(Project).where(Project.id == project_id))
    project = res.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    return PipelineStatusResponse(
        project_id=project.id,
        status=project.status,
        current_stage=project.current_stage or "INITIALIZING",
        progress_percentage=project.progress_percentage or 0,
        error_message=project.error_message,
        active_workers=1 if project.status in ["PROCESSING", "BURNING"] else 0
    )
