import csv
import io
import json
import logging
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete, func

from app.database import get_db
from app.models.speaker import SpeakerProfile, RelationshipMatrix
from app.models.subtitle import SubtitleCue
from app.schemas.speaker import (
    SpeakerProfileCreate, SpeakerProfileUpdate, SpeakerProfileResponse,
    RelationshipMatrixCreate, RelationshipMatrixUpdate, RelationshipMatrixResponse,
    SpeakerMatrixFullResponse, ApplySpeakerPresetRequest, SpeakerImportRequest
)
from app.constants.presets import GENRE_PRESETS

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/projects/{project_id}/speakers", tags=["Speakers & Relationships"])


@router.get("", response_model=SpeakerMatrixFullResponse)
async def get_speaker_matrix(
    project_id: str,
    db: AsyncSession = Depends(get_db)
):
    """Retrieve all speaker profiles with dialogue counts and relationship matrix pairs."""
    spk_res = await db.execute(
        select(SpeakerProfile).where(SpeakerProfile.project_id == project_id).order_by(SpeakerProfile.speaker_tag)
    )
    speakers = spk_res.scalars().all()

    # Get dialogue counts per speaker
    count_res = await db.execute(
        select(SubtitleCue.speaker_tag, func.count(SubtitleCue.id))
        .where(SubtitleCue.project_id == project_id)
        .group_by(SubtitleCue.speaker_tag)
    )
    counts = dict(count_res.all())

    spk_responses = []
    for s in speakers:
        resp = SpeakerProfileResponse.model_validate(s)
        resp.dialogue_count = counts.get(s.speaker_tag, 0)
        spk_responses.append(resp)

    rel_res = await db.execute(select(RelationshipMatrix).where(RelationshipMatrix.project_id == project_id))
    relationships = rel_res.scalars().all()

    return SpeakerMatrixFullResponse(
        speakers=spk_responses,
        relationships=[RelationshipMatrixResponse.model_validate(r) for r in relationships]
    )


@router.post("", response_model=SpeakerProfileResponse, status_code=201)
async def create_speaker_profile(
    project_id: str,
    data: SpeakerProfileCreate,
    db: AsyncSession = Depends(get_db)
):
    """Add a new speaker profile."""
    existing = (await db.execute(
        select(SpeakerProfile).where(
            SpeakerProfile.project_id == project_id,
            SpeakerProfile.speaker_tag == data.speaker_tag
        )
    )).scalar_one_or_none()
    
    if existing:
        existing.display_name = data.display_name or existing.display_name
        existing.original_name = data.original_name or existing.original_name
        existing.aliases = data.aliases or existing.aliases
        existing.avatar_color = data.avatar_color or existing.avatar_color
        existing.gender = data.gender or existing.gender
        existing.age_group = data.age_group or existing.age_group
        existing.role = data.role or existing.role
        existing.tone = data.tone or existing.tone
        existing.tts_voice = data.tts_voice or existing.tts_voice
        existing.tts_speed = data.tts_speed or existing.tts_speed
        existing.notes = data.notes or existing.notes
        await db.commit()
        await db.refresh(existing)
        return existing

    spk = SpeakerProfile(
        project_id=project_id,
        speaker_tag=data.speaker_tag,
        display_name=data.display_name,
        original_name=data.original_name,
        aliases=data.aliases,
        avatar_color=data.avatar_color or "#6366f1",
        gender=data.gender,
        age_group=data.age_group,
        role=data.role,
        tone=data.tone,
        tts_voice=data.tts_voice or "vi-VN-HoaiMyNeural",
        tts_speed=data.tts_speed or 1.0,
        notes=data.notes
    )
    db.add(spk)
    await db.commit()
    await db.refresh(spk)
    return spk


# STATIC ROUTES DEFINED BEFORE DYNAMIC /{speaker_tag}
@router.post("/apply-preset", response_model=SpeakerMatrixFullResponse)
async def apply_speaker_preset(
    project_id: str,
    payload: ApplySpeakerPresetRequest,
    db: AsyncSession = Depends(get_db)
):
    """Apply curated speaker profiles & relationship matrix from a genre preset."""
    preset = GENRE_PRESETS.get(payload.preset_key)
    if not preset:
        raise HTTPException(status_code=404, detail=f"Preset '{payload.preset_key}' not found")

    if payload.override_existing:
        await db.execute(delete(RelationshipMatrix).where(RelationshipMatrix.project_id == project_id))
        await db.execute(delete(SpeakerProfile).where(SpeakerProfile.project_id == project_id))

    # Add / Update Speakers
    for spk_data in preset.get("speakers", []):
        existing = (await db.execute(
            select(SpeakerProfile).where(
                SpeakerProfile.project_id == project_id,
                SpeakerProfile.speaker_tag == spk_data["speaker_tag"]
            )
        )).scalar_one_or_none()

        if existing:
            for k, v in spk_data.items():
                setattr(existing, k, v)
        else:
            db.add(SpeakerProfile(project_id=project_id, **spk_data))

    # Add / Update Relationships
    for rel_data in preset.get("relationships", []):
        existing_rel = (await db.execute(
            select(RelationshipMatrix).where(
                RelationshipMatrix.project_id == project_id,
                RelationshipMatrix.source_speaker == rel_data["source_speaker"],
                RelationshipMatrix.target_speaker == rel_data["target_speaker"]
            )
        )).scalar_one_or_none()

        if existing_rel:
            for k, v in rel_data.items():
                setattr(existing_rel, k, v)
        else:
            db.add(RelationshipMatrix(project_id=project_id, **rel_data))

    await db.commit()
    return await get_speaker_matrix(project_id, db)


@router.get("/export")
async def export_speakers(
    project_id: str,
    format: str = Query("json", regex="^(json|csv)$"),
    db: AsyncSession = Depends(get_db)
):
    """Export speaker profiles and relationship matrix as JSON or CSV."""
    spk_res = await db.execute(select(SpeakerProfile).where(SpeakerProfile.project_id == project_id))
    speakers = spk_res.scalars().all()

    rel_res = await db.execute(select(RelationshipMatrix).where(RelationshipMatrix.project_id == project_id))
    relationships = rel_res.scalars().all()

    if format == "json":
        export_data = {
            "project_id": project_id,
            "speakers": [
                {
                    "speaker_tag": s.speaker_tag,
                    "display_name": s.display_name,
                    "original_name": s.original_name,
                    "aliases": s.aliases,
                    "avatar_color": s.avatar_color,
                    "gender": s.gender,
                    "age_group": s.age_group,
                    "role": s.role,
                    "tone": s.tone,
                    "tts_voice": s.tts_voice,
                    "tts_speed": s.tts_speed,
                    "notes": s.notes
                }
                for s in speakers
            ],
            "relationships": [
                {
                    "source_speaker": r.source_speaker,
                    "target_speaker": r.target_speaker,
                    "self_pronoun": r.self_pronoun,
                    "target_pronoun": r.target_pronoun,
                    "relationship_type": r.relationship_type,
                    "honorific_notes": r.honorific_notes
                }
                for r in relationships
            ]
        }
        return Response(
            content=json.dumps(export_data, ensure_ascii=False, indent=2),
            media_type="application/json",
            headers={"Content-Disposition": f"attachment; filename=speakers_{project_id[:8]}.json"}
        )

    # CSV Format (Speakers sheet)
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "speaker_tag", "display_name", "original_name", "aliases", 
        "gender", "age_group", "role", "tone", "tts_voice", "notes"
    ])
    for s in speakers:
        writer.writerow([
            s.speaker_tag, s.display_name or "", s.original_name or "", s.aliases or "",
            s.gender or "", s.age_group or "", s.role or "", s.tone or "", s.tts_voice or "", s.notes or ""
        ])

    return Response(
        content=output.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=speakers_{project_id[:8]}.csv"}
    )


@router.post("/import", response_model=SpeakerMatrixFullResponse)
async def import_speakers(
    project_id: str,
    payload: SpeakerImportRequest,
    db: AsyncSession = Depends(get_db)
):
    """Import speaker profiles and relationship matrix from JSON payload."""
    if payload.override_existing:
        await db.execute(delete(RelationshipMatrix).where(RelationshipMatrix.project_id == project_id))
        await db.execute(delete(SpeakerProfile).where(SpeakerProfile.project_id == project_id))

    for spk_data in payload.speakers or []:
        existing = (await db.execute(
            select(SpeakerProfile).where(
                SpeakerProfile.project_id == project_id,
                SpeakerProfile.speaker_tag == spk_data.speaker_tag
            )
        )).scalar_one_or_none()

        if existing:
            for k, v in spk_data.model_dump(exclude_unset=True).items():
                setattr(existing, k, v)
        else:
            db.add(SpeakerProfile(project_id=project_id, **spk_data.model_dump()))

    for rel_data in payload.relationships or []:
        existing_rel = (await db.execute(
            select(RelationshipMatrix).where(
                RelationshipMatrix.project_id == project_id,
                RelationshipMatrix.source_speaker == rel_data.source_speaker,
                RelationshipMatrix.target_speaker == rel_data.target_speaker
            )
        )).scalar_one_or_none()

        if existing_rel:
            for k, v in rel_data.model_dump(exclude_unset=True).items():
                setattr(existing_rel, k, v)
        else:
            db.add(RelationshipMatrix(project_id=project_id, **rel_data.model_dump()))

    await db.commit()
    return await get_speaker_matrix(project_id, db)


# Pronoun Relationships
@router.get("/relationships", response_model=List[RelationshipMatrixResponse])
async def list_relationships(
    project_id: str,
    db: AsyncSession = Depends(get_db)
):
    """Retrieve all pronoun relationship pairs for a project."""
    res = await db.execute(select(RelationshipMatrix).where(RelationshipMatrix.project_id == project_id))
    return [RelationshipMatrixResponse.model_validate(r) for r in res.scalars().all()]


@router.post("/relationships", response_model=RelationshipMatrixResponse, status_code=201)
async def upsert_relationship(
    project_id: str,
    data: RelationshipMatrixCreate,
    db: AsyncSession = Depends(get_db)
):
    """Create or update a pronoun relationship between two speakers."""
    res = await db.execute(
        select(RelationshipMatrix).where(
            RelationshipMatrix.project_id == project_id,
            RelationshipMatrix.source_speaker == data.source_speaker,
            RelationshipMatrix.target_speaker == data.target_speaker
        )
    )
    rel = res.scalar_one_or_none()
    if not rel:
        rel = RelationshipMatrix(
            project_id=project_id,
            source_speaker=data.source_speaker,
            target_speaker=data.target_speaker,
            self_pronoun=data.self_pronoun,
            target_pronoun=data.target_pronoun,
            relationship_type=data.relationship_type,
            honorific_notes=data.honorific_notes
        )
        db.add(rel)
    else:
        rel.self_pronoun = data.self_pronoun
        rel.target_pronoun = data.target_pronoun
        rel.relationship_type = data.relationship_type
        rel.honorific_notes = data.honorific_notes

    await db.commit()
    await db.refresh(rel)
    return rel


@router.delete("/relationships/{relationship_id}")
async def delete_relationship(
    project_id: str,
    relationship_id: str,
    db: AsyncSession = Depends(get_db)
):
    """Delete a pronoun relationship pair."""
    res = await db.execute(
        select(RelationshipMatrix).where(
            RelationshipMatrix.id == relationship_id,
            RelationshipMatrix.project_id == project_id
        )
    )
    rel = res.scalar_one_or_none()
    if not rel:
        raise HTTPException(status_code=404, detail="Relationship not found")

    await db.delete(rel)
    await db.commit()
    return {"success": True, "message": "Relationship pair deleted"}


# DYNAMIC ROUTES WITH /{speaker_tag}
@router.get("/{speaker_tag}", response_model=SpeakerProfileResponse)
async def get_speaker_profile(
    project_id: str,
    speaker_tag: str,
    db: AsyncSession = Depends(get_db)
):
    """Retrieve an existing speaker profile by tag."""
    res = await db.execute(
        select(SpeakerProfile).where(
            SpeakerProfile.project_id == project_id,
            SpeakerProfile.speaker_tag == speaker_tag
        )
    )
    spk = res.scalar_one_or_none()
    if not spk:
        raise HTTPException(status_code=404, detail="Speaker not found")
    return spk


@router.patch("/{speaker_tag}", response_model=SpeakerProfileResponse)
async def update_speaker_profile(
    project_id: str,
    speaker_tag: str,
    data: SpeakerProfileUpdate,
    db: AsyncSession = Depends(get_db)
):
    """Update an existing speaker profile."""
    res = await db.execute(
        select(SpeakerProfile).where(
            SpeakerProfile.project_id == project_id,
            SpeakerProfile.speaker_tag == speaker_tag
        )
    )
    spk = res.scalar_one_or_none()
    if not spk:
        raise HTTPException(status_code=404, detail="Speaker not found")

    for k, v in data.model_dump(exclude_unset=True).items():
        setattr(spk, k, v)

    await db.commit()
    await db.refresh(spk)
    return spk


@router.delete("/{speaker_tag}")
async def delete_speaker_profile(
    project_id: str,
    speaker_tag: str,
    db: AsyncSession = Depends(get_db)
):
    """Delete an existing speaker profile and its associated pronoun relationships."""
    res = await db.execute(
        select(SpeakerProfile).where(
            SpeakerProfile.project_id == project_id,
            SpeakerProfile.speaker_tag == speaker_tag
        )
    )
    spk = res.scalar_one_or_none()
    if not spk:
        raise HTTPException(status_code=404, detail="Speaker not found")

    # Delete relationships involving this speaker
    await db.execute(
        delete(RelationshipMatrix).where(
            RelationshipMatrix.project_id == project_id,
            (RelationshipMatrix.source_speaker == speaker_tag) | (RelationshipMatrix.target_speaker == speaker_tag)
        )
    )

    await db.delete(spk)
    await db.commit()
    return {"success": True, "message": f"Speaker {speaker_tag} and its relationships deleted"}
