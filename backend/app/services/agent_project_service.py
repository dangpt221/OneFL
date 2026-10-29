"""Owned project adapters: Agent tools share the application's durable queue."""
import asyncio
from pathlib import Path
import time
from typing import Any
import uuid

from fastapi import BackgroundTasks, HTTPException
from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.contracts import normalize_cues
from app.config import settings
from app.database import get_async_session
from app.models.job import Job
from app.models.project import Project
from app.models.subtitle import SubtitleCue
from app.security import current_user


async def owned_project(db: AsyncSession, project_id: str) -> Project:
    project = await db.get(Project, project_id, populate_existing=True)
    if not project or project.user_id != current_user.get():
        raise HTTPException(404, 'Project not found')
    return project


async def resolve_project(db: AsyncSession, args: dict[str, Any]) -> Project:
    pid = args.get('project_id')
    for key in ('video_path', 'audio_path', 'subtitle_path', 'output_path'):
        if not args.get(key):
            continue
        path = Path(args[key]).resolve()
        matched = False
        for root in (settings.OUTPUT_DIR, settings.UPLOAD_DIR):
            if path.is_relative_to(root.resolve()):
                parts = path.relative_to(root.resolve()).parts
                if len(parts) < 2 or (pid and pid != parts[0]):
                    raise HTTPException(404, 'Media path does not belong to this project')
                pid = parts[0]
                matched = True
                break
        if not matched:
            raise HTTPException(404, 'Project media not found')
    if not pid:
        raise ValueError('Provide project_id or an owned project media path')
    return await owned_project(db, pid)


def subtitle_content(cues: list[dict], fmt: str, preset: str, bilingual: bool) -> str:
    from app.services.subtitle_generator import subtitle_generator
    if fmt == 'ass':
        return subtitle_generator.generate_ass(cues, preset=preset, bilingual=bilingual)
    rows = cues
    if bilingual:
        rows = [{**c, 'translated_text': '\n'.join(dict.fromkeys(
            t for t in (c.get('original_text'), c.get('translated_text')) if t))} for c in cues]
    return (subtitle_generator.generate_vtt if fmt == 'vtt' else subtitle_generator.generate_srt)(rows)


async def saved_cues(db: AsyncSession, pid: str, offset: int = 0, limit: int | None = None) -> list[dict]:
    query = select(SubtitleCue).where(SubtitleCue.project_id == pid).order_by(SubtitleCue.cue_index).offset(offset)
    if limit is not None:
        query = query.limit(limit)
    rows = (await db.scalars(query)).all()
    return [{key: getattr(c, key) for key in ('cue_index', 'start_time', 'end_time', 'original_text',
            'translated_text', 'speaker_tag', 'is_edited')} for c in rows]


async def export_project(args: dict[str, Any]) -> dict[str, Any]:
    from app.services.project_changes import commit_project_changes
    from app.services.storage_service import storage_service
    if args.get('cues') is not None:
        raise ValueError('Project export uses saved cues; omit cues')
    async with get_async_session() as db:
        project = await owned_project(db, args['project_id'])
        if project.active_job_id:
            raise HTTPException(409, 'Wait for the active job before exporting')
        cues = await saved_cues(db, project.id)
        if not cues:
            raise ValueError('Project has no subtitle cues')
        content = subtitle_content(cues, args['format'], args['preset'], args['bilingual'])
        path = storage_service.get_project_dir(project.id) / f'subtitles_agent_{uuid.uuid4().hex}.{args["format"]}'
        try:
            await asyncio.to_thread(path.write_text, content, encoding='utf-8')
            if args['format'] in {'ass', 'srt'}:
                setattr(project, 'subtitles_' + args['format'] + '_path', str(path))
            await commit_project_changes(db, project.id)
        except BaseException:
            path.unlink(missing_ok=True)
            raise
        await db.refresh(project)
        return {'format': args['format'], 'subtitle_path': str(path), 'artifact_url': storage_service.get_relative_url(path),
                'project_id': project.id, 'content_revision': project.content_revision, 'cues_count': len(cues)}


async def submit_media_tool(operation: str, args: dict[str, Any]) -> dict[str, Any]:
    from app.services.job_service import job_service
    from app.services.private_media import authorize_media_path
    from app.services.storage_service import storage_service
    async with get_async_session() as db:
        project = await resolve_project(db, args)
        if project.active_job_id:
            raise HTTPException(409, 'Project already has an active job')
        payload = dict(args)
        payload['project_id'] = project.id
        if operation == 'TRANSCRIBE':
            count = await db.scalar(select(func.count(SubtitleCue.id)).where(SubtitleCue.project_id == project.id))
            if count and not args.get('force_reprocess'):
                raise HTTPException(409, 'Existing cues require force_reprocess=true to replace')
            payload['source_language'] = args.get('source_language') or project.source_language
            payload['video_path'] = args.get('video_path') or project.local_video_path
            payload['audio_path'] = args.get('audio_path')
            if not payload['audio_path']:
                payload['audio_output_path'] = str(storage_service.get_project_dir(project.id) / f'extracted_agent_{uuid.uuid4().hex}.wav')
            source = payload['audio_path'] or payload['video_path']
            if not source or not Path(source).is_file():
                raise FileNotFoundError('Source media is missing')
        elif operation == 'BURN_FILE':
            payload['video_path'] = args.get('video_path') or project.dubbed_video_path or project.local_video_path
            payload['subtitle_path'] = args.get('subtitle_path') or project.subtitles_ass_path
            for key in ('video_path', 'subtitle_path'):
                if not payload[key] or not Path(payload[key]).is_file():
                    raise FileNotFoundError(f'{key} is missing; export ASS before burning')
            if Path(payload['subtitle_path']).suffix.lower() != '.ass':
                raise ValueError('Burn requires an exported ASS subtitle file')
            output = Path(args['output_path']) if args.get('output_path') else storage_service.get_project_dir(project.id) / f'burned_agent_{uuid.uuid4().hex}.mp4'
            if output.exists() or output.suffix.lower() != '.mp4':
                raise ValueError('Output must be a new MP4 path')
            if not output.resolve().is_relative_to((settings.OUTPUT_DIR / project.id).resolve()):
                raise ValueError('Output must be inside the project output directory')
            payload['output_path'] = str(output)
        else:
            raise ValueError('Unsupported Agent media operation')
        for key in ('video_path', 'audio_path', 'subtitle_path', 'output_path'):
            if payload.get(key):
                await authorize_media_path(Path(payload[key]))
        job = await job_service.enqueue(db, project.id, 'AGENT_TOOL', {'operation': operation, 'arguments': payload})
        return {'status': 'QUEUED', 'job_id': job.id, 'project_id': project.id,
                'message': 'Job accepted; use wait_for_job/get_job_status before claiming completion'}


async def execute_media_job(db: AsyncSession, pid: str, operation: str, args: dict[str, Any]) -> dict[str, Any]:
    from app.services.asr_service import asr_service
    from app.services.audio_service import audio_service
    from app.services.media_process import probe_media
    from app.services.private_media import authorize_media_path
    from app.services.project_changes import commit_project_changes
    from app.services.storage_service import storage_service
    from app.services.video_burner import video_burner
    project = await owned_project(db, pid)
    for key in ('video_path', 'audio_path', 'subtitle_path', 'output_path'):
        if args.get(key):
            await authorize_media_path(Path(args[key]))
    project.status = 'BURNING' if operation == 'BURN_FILE' else 'PROCESSING'
    project.current_stage = 'BURNING' if operation == 'BURN_FILE' else 'INGESTING'
    project.progress_percentage = 10
    await db.commit()
    if operation == 'TRANSCRIBE':
        if args.get('audio_path'):
            audio = Path(args['audio_path'])
        else:
            video = Path(args['video_path'])
            project.video_duration_seconds = await probe_media(video, require_video=True)
            audio = Path(args['audio_output_path'])
            reusable = False
            if audio.is_file():
                try:
                    reusable = abs(await probe_media(audio, require_audio=True) - project.video_duration_seconds) <= .5
                except RuntimeError:
                    reusable = False
            if not reusable:
                await audio_service.extract_audio_16k_mono(video, audio)
            project.extracted_audio_path = str(audio)
        project.current_stage = 'ASR_PROCESSING'
        project.progress_percentage = 25
        await db.commit()
        cues = normalize_cues(await asr_service.transcribe_audio(audio_path=audio, source_language=args['source_language']))
        if not cues:
            raise ValueError('No speech detected')
        from app.models.speaker import RelationshipMatrix, SpeakerProfile
        await db.execute(delete(SubtitleCue).where(SubtitleCue.project_id == pid))
        await db.execute(delete(RelationshipMatrix).where(RelationshipMatrix.project_id == pid))
        await db.execute(delete(SpeakerProfile).where(SpeakerProfile.project_id == pid))
        for c in cues:
            db.add(SubtitleCue(project_id=pid, **{k: c[k] for k in ('cue_index', 'start_time', 'end_time', 'original_text', 'speaker_tag')}))
        project.extracted_audio_path = str(audio)
        project.subtitles_ass_path = project.subtitles_srt_path = None
        project.status, project.current_stage = 'WAITING_REVIEW', 'ASR_COMPLETE'
        project.progress_percentage, project.error_message = 100, None
        await commit_project_changes(db, pid, invalidate_audio=True, allow_active_job=True)
        await db.refresh(project)
        return {'audio_path': str(audio), 'total_cues': len(cues), 'cues_sample': cues[:5],
                'content_revision': project.content_revision, 'project_id': pid}
    if operation != 'BURN_FILE':
        raise ValueError('Unsupported Agent media operation')
    output = Path(args['output_path'])
    if output.exists():
        raise ValueError('Output already exists; refusing to overwrite an artifact')
    partial = output.with_name(output.stem + '.partial.mp4')
    try:
        await video_burner.burn_subtitles_to_video(Path(args['video_path']), Path(args['subtitle_path']), partial,
                                                  clean_chinese_mode=args['clean_chinese_mode'])
        duration = await probe_media(partial, require_video=True)
        expected = await probe_media(Path(args['video_path']), require_video=True)
        if abs(duration - expected) > .5:
            raise ValueError('Rendered duration does not match source')
        partial.replace(output)
    finally:
        partial.unlink(missing_ok=True)
    project.burned_video_path, project.burned_video_url = str(output), storage_service.get_relative_url(output)
    project.status, project.current_stage, project.progress_percentage = 'COMPLETED', 'COMPLETED', 100
    project.error_message = None
    await commit_project_changes(db, pid, allow_active_job=True)
    await db.refresh(project)
    return {'output_path': str(output), 'output_url': project.burned_video_url,
            'project_id': pid, 'content_revision': project.content_revision}


async def project_context(args: dict[str, Any]) -> dict[str, Any]:
    async with get_async_session() as db:
        p = await owned_project(db, args['project_id'])
        total = await db.scalar(select(func.count(SubtitleCue.id)).where(SubtitleCue.project_id == p.id))
        rows = await saved_cues(db, p.id, args.get('offset', 0), args.get('limit', 50))
        return {**{k: getattr(p, k) for k in ('id', 'status', 'current_stage', 'progress_percentage', 'active_job_id',
                'content_revision', 'original_video_url', 'burned_video_url', 'dubbed_video_url', 'error_message')},
                'project_id': p.id, 'total_cues': total, 'offset': args.get('offset', 0), 'cues': rows}


async def start_pipeline(args: dict[str, Any]) -> dict[str, Any]:
    from app.api.v1.pipeline import trigger_pipeline
    from app.schemas.translation import PipelineTriggerRequest
    async with get_async_session() as db:
        await owned_project(db, args['project_id'])
        result = await trigger_pipeline(args['project_id'], PipelineTriggerRequest(**{k: v for k, v in args.items() if k != 'project_id'}), BackgroundTasks(), db)
        return {**result, 'status': 'QUEUED', 'project_id': args['project_id']}


async def start_dubbing(args: dict[str, Any]) -> dict[str, Any]:
    from app.api.v1.tts import start_project_dubbing
    from app.schemas.tts import ProjectDubRequest
    async with get_async_session() as db:
        await owned_project(db, args['project_id'])
        return await start_project_dubbing(args['project_id'], BackgroundTasks(), ProjectDubRequest(**{k: v for k, v in args.items() if k != 'project_id'}), db)


async def job_status(args: dict[str, Any]) -> dict[str, Any]:
    async with get_async_session() as db:
        p = await owned_project(db, args['project_id'])
        job = await db.get(Job, args['job_id'])
        if not job or job.project_id != p.id:
            raise HTTPException(404, 'Job not found')
        return {'success': job.status not in {'FAILED', 'CANCELLED'}, 'status': job.status, 'job_id': job.id,
                'project_id': p.id, 'error': job.error, 'result': job.result,
                'artifact_current': bool(job.result) and job.result.get('content_revision') == p.content_revision}


async def wait_job(args: dict[str, Any]) -> dict[str, Any]:
    deadline = time.monotonic() + args.get('timeout_seconds', 5)
    while True:
        result = await job_status(args)
        remaining = deadline - time.monotonic()
        if result['status'] not in {'QUEUED', 'RUNNING'} or remaining <= 0:
            return result
        await asyncio.sleep(min(.2, remaining))


async def cancel_project(args: dict[str, Any]) -> dict[str, Any]:
    from app.services.job_service import job_service
    async with get_async_session() as db:
        project = await owned_project(db, args['project_id'])
        job_id = project.active_job_id
        await job_service.cancel(db, project.id)
        job = await db.get(Job, job_id, populate_existing=True) if job_id else None
        if job and job.status == 'CANCELLED':
            await db.execute(update(Project).where(Project.id == project.id, Project.active_job_id.is_(None)).values(
                status='CANCELLED', current_stage='CANCELLED', error_message=None))
            await db.commit()
        await db.refresh(project)
        return {'project_id': project.id, 'job_id': job_id, 'status': project.status,
                'active_job_id': project.active_job_id}


async def verify_artifact(project_id: str, expected: str) -> bool:
    """Check current persisted outputs, independently of the model's final sentence."""
    async with get_async_session() as db:
        p = await owned_project(db, project_id)
        if p.active_job_id or p.status in {'FAILED', 'CANCELLED'}:
            return False
        if expected in {'burned_video', 'dubbed_video', 'subtitles'}:
            path = getattr(p, {'burned_video': 'burned_video_path', 'dubbed_video': 'dubbed_video_path',
                               'subtitles': 'subtitles_ass_path'}[expected])
            return bool(path) and Path(path).is_file()
        if expected not in {'transcript', 'translated_cues'}:
            raise ValueError('Unknown expected_artifact')
        total = await db.scalar(select(func.count(SubtitleCue.id)).where(SubtitleCue.project_id == p.id))
        if not total:
            return False
        if expected == 'translated_cues':
            missing = await db.scalar(select(func.count(SubtitleCue.id)).where(SubtitleCue.project_id == p.id,
                (SubtitleCue.translated_text.is_(None)) | (func.trim(SubtitleCue.translated_text) == '')))
            return missing == 0
        return True
