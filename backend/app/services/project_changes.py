"""Publish durable content revisions for mutations made by any API process."""
from sqlalchemy import update, case
from fastapi import HTTPException
from app.models.project import Project


async def commit_project_changes(db, project_id: str, *, invalidate_audio: bool = False, allow_active_job: bool = False):
    await db.flush()
    values = {'content_revision': Project.content_revision + 1}
    if invalidate_audio:
        if not allow_active_job:
            values['last_job_kind'] = None
        values.update({field: None for field in (
            'burned_video_path', 'burned_video_url', 'dubbed_audio_path',
            'dubbed_audio_url', 'dubbed_video_path', 'dubbed_video_url',
        )})
        values.update(status=case((Project.status == 'COMPLETED', 'WAITING_REVIEW'), else_=Project.status),
                      current_stage=case((Project.status == 'COMPLETED', 'WAITING_REVIEW'), else_=Project.current_stage))
    statement = update(Project).where(Project.id == project_id)
    if not allow_active_job:
        statement = statement.where(Project.active_job_id.is_(None))
    result = await db.execute(statement.values(**values))
    if result.rowcount != 1:
        await db.rollback()
        raise HTTPException(409, 'Project changed or a job started; refresh before editing')
    await db.commit()
