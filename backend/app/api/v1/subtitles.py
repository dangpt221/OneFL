import logging
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete

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
            select(SubtitleCue).where(SubtitleCue.project_id == project_id).order_by(SubtitleCue.cue_index)
        )
        cues = cues_res.scalars().all()
        if not cues:
            return

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
        logger.warning(f"Failed to auto-sync subtitle files on disk for project {project_id}: {e}")



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
    stmt = stmt.order_by(SubtitleCue.cue_index).offset(skip)
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
    duration = max(0.1, data.end_time - data.start_time)
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
    await db.commit()
    await db.refresh(cue)
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

    await db.delete(cue)
    await db.commit()
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

    await db.commit()
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



@router.post("/retranslate", response_model=List[SubtitleCueResponse])
async def retranslate_cues(
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
            ).order_by(SubtitleCue.cue_index)
        )
    else:
        cues_res = await db.execute(
            select(SubtitleCue).where(
                SubtitleCue.project_id == project_id,
                SubtitleCue.id.in_(req.cue_ids)
            ).order_by(SubtitleCue.cue_index)
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
            "context_note": g.context_note
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
        custom_instructions=req.custom_instruction
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
            c.is_edited = True
            updated_items.append(c)

    await db.commit()
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
        .order_by(SubtitleCue.cue_index)
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
