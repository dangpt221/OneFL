import logging
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import get_db, get_async_session
from app.models.project import Project
from app.schemas.translation import PipelineTriggerRequest, PipelineStatusResponse
from app.services.workflow_engine import workflow_engine

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

    async def run_bg(pid: str, stg: str):
        async with get_async_session() as bg_db:
            await workflow_engine.run_pipeline(bg_db, pid, start_stage=stg)

    background_tasks.add_task(run_bg, project_id, req.stage)
    return {"success": True, "message": f"Pipeline triggered at stage: {req.stage or 'FULL'}"}


from pydantic import BaseModel, Field
from typing import Optional


class BurnOptionsRequest(BaseModel):
    subtitle_preset: Optional[str] = Field("box_banner", description="Style preset: box_banner, cinema, yellow_highlight")
    bilingual: Optional[bool] = Field(False, description="Enable dual bilingual subtitles")
    mask_original_sub: Optional[bool] = Field(True, description="Conceal original foreign hardsubs")


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

    if req:
        existing_cfg = project.settings_override or {}
        existing_cfg.update(req.model_dump(exclude_unset=True))
        project.settings_override = existing_cfg
        await db.commit()

    async def run_burn_bg(pid: str):
        async with get_async_session() as bg_db:
            await workflow_engine.burn_project_video(bg_db, pid)

    background_tasks.add_task(run_burn_bg, project_id)
    return {"success": True, "message": "Video burning initiated"}


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
