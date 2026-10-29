"""Invalidate references when inputs change; retain files until explicit cleanup."""

def invalidate_artifacts(project, *, audio: bool = False) -> None:
    project.burned_video_path = None
    project.burned_video_url = None
    if audio:
        project.dubbed_audio_path = None
        project.dubbed_audio_url = None
        project.dubbed_video_path = None
        project.dubbed_video_url = None


async def cleanup_expired_scratch(db) -> int:
    """Remove old generated scratch only when no job is using media resources."""
    import asyncio
    import time
    from sqlalchemy import select, func
    from app.config import settings
    from app.models.job import Job
    from app.models.project import Project
    if await db.scalar(select(func.count(Job.id)).where(Job.status.in_(['RUNNING', 'QUEUED']))):
        return 0
    cutoff = time.time() - max(1, settings.CACHE_RETENTION_DAYS) * 86400
    root = settings.TEMP_SCRATCH_DIR.resolve()
    projects = (await db.execute(select(Project))).scalars().all()
    protected = {__import__('pathlib').Path(getattr(project, field)).resolve()
                 for project in projects
                 for field in ('local_video_path', 'extracted_audio_path', 'burned_video_path', 'dubbed_audio_path', 'dubbed_video_path', 'subtitles_ass_path', 'subtitles_srt_path')
                 if getattr(project, field, None)}
    protected.update(__import__('pathlib').Path(project.dubbed_audio_path).with_suffix('.timing.json').resolve()
                     for project in projects if project.dubbed_audio_path)
    def remove_expired():
        removed = 0
        for directory in (root, settings.OUTPUT_DIR.resolve()):
            for path in directory.rglob('*'):
                if path.name.startswith('.') or path.suffix == '.lock':
                    continue
                if path.is_file() and not path.is_symlink() and path.resolve().is_relative_to(directory) and path.resolve() not in protected:
                    if path.stat().st_mtime < cutoff:
                        path.unlink()
                        removed += 1
        return removed
    return await asyncio.to_thread(remove_expired)
