from app.services.project_changes import commit_project_changes
import logging
from pathlib import Path
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete, func
from app.services.artifact_service import invalidate_artifacts
from app.services.job_service import job_service

from app.database import get_db
from app.models.project import Project
from app.models.subtitle import SubtitleCue
from app.models.speaker import SpeakerProfile, RelationshipMatrix
from app.models.glossary import GlossaryTerm
from app.schemas.subtitle import SubtitleCueCreate, SubtitleCueUpdate, SubtitleCueResponse, SubtitleListResponse, BatchSubtitleUpdate
from app.schemas.translation import RetranslateRequest
from app.services.guardrails import SubtitleGuardrails
from app.services.subtitle_generator import subtitle_generator
from app.services.translation_service import translation_service
from app.services.storage_service import storage_service
from app.services.ws_manager import ws_manager


logger = logging.getLogger(__name__)
router = APIRouter(prefix="/projects/{project_id}/subtitles", tags=["Subtitles"])


async def sync_subtitles_on_disk(project_id: str, db: AsyncSession):
    """Regenerates subtitles.ass and subtitles.srt on disk whenever cues are modified in the DB."""
    try:
        proj_res = await db.execute(select(Project).where(Project.id == project_id))
        project = proj_res.scalar_one_or_none()
        if not project:
            return

        cues_res = await db.execute(
            select(SubtitleCue).where(SubtitleCue.project_id == project_id).order_by(SubtitleCue.start_time, SubtitleCue.cue_index)
        )
        cues = cues_res.scalars().all()

        cues_data = [
            {
                "start_time": c.start_time,
                "end_time": c.end_time,
                "original_text": c.original_text,
                "translated_text": c.translated_text or c.original_text,
                "speaker_tag": c.speaker_tag
            }
            for c in cues
        ]

        proj_cfg = project.settings_override or {}
        bilingual = proj_cfg.get("bilingual", False)
        preset = proj_cfg.get("subtitle_preset", "box_banner")

        p_dir = storage_service.get_project_dir(project_id)
        ass_path = p_dir / "subtitles.ass"
        srt_path = p_dir / "subtitles.srt"

        ass_content = subtitle_generator.generate_ass(cues_data, bilingual=bilingual, preset=preset)
        srt_content = subtitle_generator.generate_srt(cues_data)

        await storage_service.write_text_file(ass_path, ass_content)
        await storage_service.write_text_file(srt_path, srt_content)

        project.subtitles_ass_path = str(ass_path)
        project.subtitles_srt_path = str(srt_path)
        await db.commit()
    except Exception as e:
        logger.exception("Subtitle synchronization failed for %s", project_id)
        raise



@router.get("", response_model=SubtitleListResponse)
async def get_project_subtitles(
    project_id: str,
    skip: int = 0,
    limit: Optional[int] = None,
    speaker_tag: Optional[str] = None,
    db: AsyncSession = Depends(get_db)
):
    """Retrieve all subtitle cues for a project in chronological order."""
    stmt = select(SubtitleCue).where(SubtitleCue.project_id == project_id)
    if speaker_tag:
        stmt = stmt.where(SubtitleCue.speaker_tag == speaker_tag)
    stmt = stmt.order_by(SubtitleCue.start_time, SubtitleCue.cue_index).offset(skip)
    if limit is not None:
        stmt = stmt.limit(limit)

    res = await db.execute(stmt)
    cues = res.scalars().all()
    return SubtitleListResponse(
        project_id=project_id,
        total_cues=len(cues),
        items=[SubtitleCueResponse.model_validate(c) for c in cues]
    )



@router.post("", response_model=SubtitleCueResponse, status_code=201)
async def create_subtitle_cue(
    project_id: str,
    data: SubtitleCueCreate,
    db: AsyncSession = Depends(get_db)
):
    """Create a new subtitle cue entry."""
    project = await db.get(Project, project_id)
    if not project:
        raise HTTPException(404, 'Project not found')
    if await db.scalar(select(func.count(SubtitleCue.id)).where(SubtitleCue.project_id == project_id, SubtitleCue.cue_index == data.cue_index)):
        raise HTTPException(409, 'Cue index already exists in this project')
    invalidate_artifacts(project, audio=True)
    duration = data.end_time - data.start_time
    text = data.translated_text or data.original_text
    cps = SubtitleGuardrails.calculate_cps(text, duration)
    lines = text.split("\n")

    cue = SubtitleCue(
        project_id=project_id,
        cue_index=data.cue_index,
        start_time=data.start_time,
        end_time=data.end_time,
        original_text=data.original_text,
        translated_text=data.translated_text,
        speaker_tag=data.speaker_tag,
        target_speaker_tag=data.target_speaker_tag,
        cps=cps,
        line_count=len(lines),
        max_line_length=max(len(l) for l in lines) if lines else 0,
        is_edited=False
    )
    db.add(cue)
    await commit_project_changes(db, project_id, invalidate_audio=True)
    await db.refresh(cue)
    await sync_subtitles_on_disk(project_id, db)
    await ws_manager.broadcast_to_project(project_id, "CUES_CHANGED", {})
    return cue


@router.get("/{cue_id}", response_model=SubtitleCueResponse)
async def get_subtitle_cue(
    project_id: str,
    cue_id: str,
    db: AsyncSession = Depends(get_db)
):
    """Retrieve a single subtitle cue."""
    res = await db.execute(
        select(SubtitleCue).where(
            SubtitleCue.id == cue_id,
            SubtitleCue.project_id == project_id
        )
    )
    cue = res.scalar_one_or_none()
    if not cue:
        raise HTTPException(status_code=404, detail="Subtitle cue not found")
    return cue


@router.delete("/{cue_id}")
async def delete_subtitle_cue(
    project_id: str,
    cue_id: str,
    db: AsyncSession = Depends(get_db)
):
    """Delete a subtitle cue."""
    res = await db.execute(
        select(SubtitleCue).where(
            SubtitleCue.id == cue_id,
            SubtitleCue.project_id == project_id
        )
    )
    cue = res.scalar_one_or_none()
    if not cue:
        raise HTTPException(status_code=404, detail="Subtitle cue not found")

    project = await db.get(Project, project_id)
    invalidate_artifacts(project, audio=True)
    await db.delete(cue)
    await commit_project_changes(db, project_id, invalidate_audio=True)
    await sync_subtitles_on_disk(project_id, db)
    await ws_manager.broadcast_to_project(project_id, 'CUES_CHANGED', {})
    return {"success": True, "message": f"Cue {cue_id} deleted"}


@router.patch("/{cue_id}", response_model=SubtitleCueResponse)
async def update_subtitle_cue(
    project_id: str,
    cue_id: str,
    data: SubtitleCueUpdate,
    db: AsyncSession = Depends(get_db)
):
    """Update a specific subtitle cue (text, timing, speaker tag)."""
    res = await db.execute(
        select(SubtitleCue).where(
            SubtitleCue.id == cue_id,
            SubtitleCue.project_id == project_id
        )
    )
    cue = res.scalar_one_or_none()
    if not cue:
        raise HTTPException(status_code=404, detail="Subtitle cue not found")

    update_dict = data.model_dump(exclude_unset=True)
    if update_dict.get('end_time', cue.end_time) <= update_dict.get('start_time', cue.start_time):
        raise HTTPException(422, 'end_time must be greater than start_time')
    project = await db.get(Project, project_id)
    if ({'start_time', 'end_time'} & update_dict.keys()) and project.video_duration_seconds:
        if update_dict.get('end_time', cue.end_time) > project.video_duration_seconds:
            raise HTTPException(422, 'Subtitle timing must stay within the source video duration')
    invalidate_artifacts(project, audio=True)
    for k, v in update_dict.items():
        setattr(cue, k, v)

    # Recalculate CPS and physical limits
    duration = cue.end_time - cue.start_time
    text = cue.translated_text or cue.original_text
    cue.cps = SubtitleGuardrails.calculate_cps(text, duration)
    lines = text.split("\n")
    cue.line_count = len(lines)
    cue.max_line_length = max(len(l) for l in lines) if lines else 0
    cue.is_edited = True

    await commit_project_changes(db, project_id, invalidate_audio=True)
    await db.refresh(cue)

    # Auto-synchronize disk subtitle files (subtitles.ass / subtitles.srt)
    await sync_subtitles_on_disk(project_id, db)

    # Broadcast update to connected studio clients
    await ws_manager.broadcast_to_project(
        project_id,
        "CUE_UPDATED",
        SubtitleCueResponse.model_validate(cue).model_dump()
    )

    return cue



async def _retranslate_cues(
    project_id: str,
    req: RetranslateRequest,
    db: AsyncSession = Depends(get_db)
):
    """Re-translate selected cues with custom AI prompt / model override."""
    proj_res = await db.execute(select(Project).where(Project.id == project_id))
    project = proj_res.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    if not req.cue_ids or (len(req.cue_ids) == 1 and req.cue_ids[0].upper() == "ALL"):
        cues_res = await db.execute(
            select(SubtitleCue).where(
                SubtitleCue.project_id == project_id
            ).order_by(SubtitleCue.start_time, SubtitleCue.cue_index)
        )
    else:
        cues_res = await db.execute(
            select(SubtitleCue).where(
                SubtitleCue.project_id == project_id,
                SubtitleCue.id.in_(req.cue_ids)
            ).order_by(SubtitleCue.start_time, SubtitleCue.cue_index)
        )
    cues = cues_res.scalars().all()
    if not cues:
        raise HTTPException(status_code=400, detail="No matching cues found to re-translate")

    # Fetch rich speaker, relationship matrix, and glossary context
    spk_res = await db.execute(select(SpeakerProfile).where(SpeakerProfile.project_id == project_id))
    speakers = {
        s.speaker_tag: {
            "name": s.display_name,
            "original_name": getattr(s, 'original_name', '') or '',
            "gender": s.gender,
            "role": s.role,
            "tone": s.tone,
            "notes": s.notes
        }
        for s in spk_res.scalars().all()
    }
    
    rel_res = await db.execute(select(RelationshipMatrix).where(RelationshipMatrix.project_id == project_id))
    rels = [
        {
            "source_speaker": r.source_speaker,
            "target_speaker": r.target_speaker,
            "self_pronoun": r.self_pronoun,
            "target_pronoun": r.target_pronoun,
            "relationship_type": r.relationship_type,
            "honorific_notes": r.honorific_notes
        }
        for r in rel_res.scalars().all()
    ]

    glo_res = await db.execute(select(GlossaryTerm).where(GlossaryTerm.project_id == project_id))
    glossary = [
        {
            "source_term": g.source_term,
            "target_term": g.target_term,
            "priority": g.priority, "case_sensitive": g.case_sensitive, "context_note": g.context_note
        }
        for g in glo_res.scalars().all()
    ]

    cues_payload = [
        {
            "cue_index": c.cue_index,
            "start_time": c.start_time,
            "end_time": c.end_time,
            "original_text": c.original_text,
            "speaker_tag": c.speaker_tag
        }
        for c in cues
    ]

    results = await translation_service.translate_project_cues(
        project_id=project_id,
        cues=cues_payload,
        source_lang=project.source_language,
        target_lang=project.target_language,
        speaker_profiles=speakers,
        relationship_matrix=rels,
        glossary=glossary,
        custom_instructions=req.custom_instruction,
        force_reprocess=True, preserve_edited=False,
        model_override=req.model_override, temperature=req.temperature,
        video_path=Path(project.local_video_path) if project.local_video_path else None,
    )

    res_map = {r["cue_index"]: r for r in results}
    updated_items = []
    for c in cues:
        if c.cue_index in res_map:
            t = res_map[c.cue_index]
            c.translated_text = t.get("translated_text")
            c.cps = t.get("cps", 0.0)
            c.line_count = t.get("line_count", 1)
            c.max_line_length = t.get("max_line_length", 0)
            c.has_guardrail_violation = t.get('has_guardrail_violation', False)
            c.violation_notes = t.get('violation_notes')
            c.is_edited = True
            updated_items.append(c)

    invalidate_artifacts(project, audio=True)
    project.status, project.current_stage = "WAITING_REVIEW", "WAITING_REVIEW"
    await commit_project_changes(db, project_id, invalidate_audio=True, allow_active_job=True)
    # Auto-synchronize disk subtitle files
    await sync_subtitles_on_disk(project_id, db)
    return updated_items



@router.get("/export/{format_type}")
async def export_subtitles(
    project_id: str,
    format_type: str,  # ass | srt | vtt
    bilingual: bool = False,
    preset: str = "box_banner",
    db: AsyncSession = Depends(get_db)
):
    """Export and download subtitle file in .ass, .srt, or .vtt format with optional bilingual & style presets."""
    cues_res = await db.execute(
        select(SubtitleCue)
        .where(SubtitleCue.project_id == project_id)
        .order_by(SubtitleCue.start_time, SubtitleCue.cue_index)
    )
    cues = cues_res.scalars().all()
    cues_data = [
        {
            "start_time": c.start_time,
            "end_time": c.end_time,
            "original_text": c.original_text,
            "translated_text": c.translated_text,
            "speaker_tag": c.speaker_tag
        }
        for c in cues
    ]

    fmt = format_type.lower()
    if fmt == "ass":
        content = subtitle_generator.generate_ass(cues_data, bilingual=bilingual, preset=preset)
        media_type = "text/x-ssa"
        filename = f"subtitles_{project_id}.ass"
    elif fmt == "srt":
        content = subtitle_generator.generate_srt(cues_data)
        media_type = "application/x-subrip"
        filename = f"subtitles_{project_id}.srt"
    elif fmt == "vtt":
        content = subtitle_generator.generate_vtt(cues_data)
        media_type = "text/vtt"
        filename = f"subtitles_{project_id}.vtt"
    else:
        raise HTTPException(status_code=400, detail="Invalid format. Supported formats: ass, srt, vtt")

    return Response(
        content=content,
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'}
    )


@router.post('/retranslate', status_code=202)
async def retranslate_cues(project_id: str, req: RetranslateRequest, db: AsyncSession = Depends(get_db)):
    if not await db.get(Project, project_id):
        raise HTTPException(404, 'Project not found')
    job = await job_service.enqueue(db, project_id, 'RETRANSLATE', req.model_dump())
    return {'success': True, 'job_id': job.id, 'status': 'QUEUED'}
