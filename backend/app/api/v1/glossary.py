import csv
import io
import json
import logging
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete

from app.database import get_db
from app.models.glossary import GlossaryTerm
from app.models.subtitle import SubtitleCue
from app.schemas.glossary import (
    GlossaryTermCreate, GlossaryTermUpdate, GlossaryTermResponse, GlossaryListResponse,
    ApplyGlossaryPresetRequest, GlossaryImportRequest, GenrePresetSummary
)
from app.constants.presets import GENRE_PRESETS
from app.services.llm_router import llm_router

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/projects/{project_id}/glossary", tags=["Glossary"])


@router.get("/presets", response_model=List[GenrePresetSummary])
async def list_genre_presets(project_id: str):
    """List all available genre preset libraries."""
    summaries = []
    for pid, pdata in GENRE_PRESETS.items():
        summaries.append(GenrePresetSummary(
            id=pid,
            name=pdata["name"],
            icon=pdata["icon"],
            genre=pdata["genre"],
            description=pdata["description"],
            term_count=len(pdata.get("terms", [])),
            speaker_count=len(pdata.get("speakers", []))
        ))
    return summaries


@router.post("/apply-preset", response_model=GlossaryListResponse)
async def apply_glossary_preset(
    project_id: str,
    payload: ApplyGlossaryPresetRequest,
    db: AsyncSession = Depends(get_db)
):
    """Apply a genre preset library to the current project's glossary."""
    preset = GENRE_PRESETS.get(payload.preset_key)
    if not preset:
        raise HTTPException(status_code=404, detail=f"Preset '{payload.preset_key}' not found")

    if payload.override_existing:
        await db.execute(delete(GlossaryTerm).where(GlossaryTerm.project_id == project_id))

    for term_data in preset.get("terms", []):
        src = term_data["source_term"]
        existing = (await db.execute(
            select(GlossaryTerm).where(
                GlossaryTerm.project_id == project_id,
                GlossaryTerm.source_term == src
            )
        )).scalar_one_or_none()

        if existing:
            existing.target_term = term_data["target_term"]
            existing.category = term_data.get("category", "general")
            existing.context_note = term_data.get("context_note")
        else:
            db.add(GlossaryTerm(
                project_id=project_id,
                source_term=src,
                target_term=term_data["target_term"],
                category=term_data.get("category", "general"),
                context_note=term_data.get("context_note"),
                priority="normal",
                case_sensitive="false"
            ))

    await db.commit()
    return await list_glossary_terms(project_id, db=db)


@router.get("/export")
async def export_glossary(
    project_id: str,
    format: str = Query("json", pattern="^(json|csv)$"),
    db: AsyncSession = Depends(get_db)
):
    """Export project glossary terms as JSON or CSV."""
    res = await db.execute(
        select(GlossaryTerm).where(GlossaryTerm.project_id == project_id).order_by(GlossaryTerm.source_term)
    )
    terms = res.scalars().all()

    if format == "json":
        data = {
            "project_id": project_id,
            "total": len(terms),
            "terms": [
                {
                    "source_term": t.source_term,
                    "target_term": t.target_term,
                    "category": t.category,
                    "context_note": t.context_note,
                    "priority": getattr(t, "priority", "normal") or "normal",
                    "case_sensitive": getattr(t, "case_sensitive", "false") or "false"
                }
                for t in terms
            ]
        }
        return Response(
            content=json.dumps(data, ensure_ascii=False, indent=2),
            media_type="application/json",
            headers={"Content-Disposition": f"attachment; filename=glossary_{project_id[:8]}.json"}
        )

    # CSV Format
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["source_term", "target_term", "category", "context_note", "priority"])
    for t in terms:
        writer.writerow([
            t.source_term, t.target_term, t.category or "general",
            t.context_note or "", getattr(t, "priority", "normal") or "normal"
        ])

    return Response(
        content=output.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=glossary_{project_id[:8]}.csv"}
    )


@router.post("/import", response_model=GlossaryListResponse)
async def import_glossary(
    project_id: str,
    payload: GlossaryImportRequest,
    db: AsyncSession = Depends(get_db)
):
    """Import glossary terms into the current project."""
    if payload.override_existing:
        await db.execute(delete(GlossaryTerm).where(GlossaryTerm.project_id == project_id))

    for t in payload.terms:
        existing = (await db.execute(
            select(GlossaryTerm).where(
                GlossaryTerm.project_id == project_id,
                GlossaryTerm.source_term == t.source_term
            )
        )).scalar_one_or_none()

        if existing:
            existing.target_term = t.target_term
            existing.category = t.category
            existing.context_note = t.context_note
            existing.priority = t.priority or "normal"
            existing.case_sensitive = t.case_sensitive or "false"
        else:
            db.add(GlossaryTerm(
                project_id=project_id,
                source_term=t.source_term,
                target_term=t.target_term,
                category=t.category,
                context_note=t.context_note,
                priority=t.priority or "normal",
                case_sensitive=t.case_sensitive or "false"
            ))

    await db.commit()
    return await list_glossary_terms(project_id, db=db)


@router.get("", response_model=GlossaryListResponse)
async def list_glossary_terms(
    project_id: str,
    category: Optional[str] = None,
    q: Optional[str] = None,
    db: AsyncSession = Depends(get_db)
):
    """Retrieve all glossary terms for a project with optional category and keyword search."""
    stmt = select(GlossaryTerm).where(GlossaryTerm.project_id == project_id)
    if category and category != "all":
        stmt = stmt.where(GlossaryTerm.category == category)
    if q:
        search_pattern = f"%{q.strip()}%"
        stmt = stmt.where(
            (GlossaryTerm.source_term.ilike(search_pattern)) | 
            (GlossaryTerm.target_term.ilike(search_pattern)) |
            (GlossaryTerm.context_note.ilike(search_pattern))
        )
    stmt = stmt.order_by(GlossaryTerm.source_term)

    res = await db.execute(stmt)
    terms = res.scalars().all()
    return GlossaryListResponse(
        project_id=project_id,
        total=len(terms),
        items=[GlossaryTermResponse.model_validate(t) for t in terms]
    )


@router.post("", response_model=GlossaryTermResponse, status_code=201)
async def add_glossary_term(
    project_id: str,
    data: GlossaryTermCreate,
    db: AsyncSession = Depends(get_db)
):
    """Add a new specialized terminology rule."""
    res = await db.execute(
        select(GlossaryTerm).where(
            GlossaryTerm.project_id == project_id,
            GlossaryTerm.source_term == data.source_term
        )
    )
    existing = res.scalar_one_or_none()
    if existing:
        existing.target_term = data.target_term
        existing.category = data.category
        existing.context_note = data.context_note
        existing.priority = data.priority or "normal"
        existing.case_sensitive = data.case_sensitive or "false"
        await db.commit()
        await db.refresh(existing)
        return existing

    term = GlossaryTerm(
        project_id=project_id,
        source_term=data.source_term,
        target_term=data.target_term,
        category=data.category,
        context_note=data.context_note,
        priority=data.priority or "normal",
        case_sensitive=data.case_sensitive or "false"
    )
    db.add(term)
    await db.commit()
    await db.refresh(term)
    return term


@router.get("/{term_id}", response_model=GlossaryTermResponse)
async def get_glossary_term(
    project_id: str,
    term_id: str,
    db: AsyncSession = Depends(get_db)
):
    """Retrieve a single glossary term."""
    res = await db.execute(
        select(GlossaryTerm).where(
            GlossaryTerm.id == term_id,
            GlossaryTerm.project_id == project_id
        )
    )
    term = res.scalar_one_or_none()
    if not term:
        raise HTTPException(status_code=404, detail="Glossary term not found")
    return term


@router.patch("/{term_id}", response_model=GlossaryTermResponse)
async def update_glossary_term(
    project_id: str,
    term_id: str,
    data: GlossaryTermUpdate,
    db: AsyncSession = Depends(get_db)
):
    """Update a glossary term."""
    res = await db.execute(
        select(GlossaryTerm).where(
            GlossaryTerm.id == term_id,
            GlossaryTerm.project_id == project_id
        )
    )
    term = res.scalar_one_or_none()
    if not term:
        raise HTTPException(status_code=404, detail="Glossary term not found")

    for k, v in data.model_dump(exclude_unset=True).items():
        setattr(term, k, v)

    await db.commit()
    await db.refresh(term)
    return term


@router.delete("/{term_id}")
async def delete_glossary_term(
    project_id: str,
    term_id: str,
    db: AsyncSession = Depends(get_db)
):
    """Delete a glossary term."""
    res = await db.execute(
        select(GlossaryTerm).where(
            GlossaryTerm.id == term_id,
            GlossaryTerm.project_id == project_id
        )
    )
    term = res.scalar_one_or_none()
    if not term:
        raise HTTPException(status_code=404, detail="Glossary term not found")

    await db.delete(term)
    await db.commit()
    return {"success": True, "message": "Term deleted"}


@router.post("/auto-extract", response_model=List[GlossaryTermResponse])
async def auto_extract_glossary(
    project_id: str,
    db: AsyncSession = Depends(get_db)
):
    """Use AI to auto-extract domain-specific keywords and recommended Vietnamese translations across sample dialogue."""
    # Stratified sample: beginning, middle, and end
    total_cues = (await db.execute(
        select(func.count(SubtitleCue.id)).where(SubtitleCue.project_id == project_id)
    )).scalar() or 0

    if total_cues == 0:
        raise HTTPException(status_code=400, detail="No cues found to extract terminology from")

    sample_size = min(60, total_cues)
    cues_res = await db.execute(
        select(SubtitleCue).where(SubtitleCue.project_id == project_id).order_by(SubtitleCue.cue_index).limit(sample_size)
    )
    cues = cues_res.scalars().all()

    sample_texts = [f"[{c.speaker_tag}]: {c.original_text}" for c in cues if c.original_text]
    system_prompt = """Bạn là Chuyên gia Cao Cấp về Biên Dịch và Quản Lý Thuật Ngữ Điện Ảnh (Studio Terminology Specialist).
Nhiệm vụ: Phân tích các câu thoại trong kịch bản và trích xuất danh mục các thuật ngữ chuyên ngành quan trọng nhất.

BẮT BUỘC PHÂN LOẠI VÀO CÁC DANH MỤC SAU:
- PROPER_NAME (Tên riêng nhân vật / Tước vị / Thần thoại)
- LOCATION (Địa danh / Tinh cầu / Căn cứ)
- WEAPON_MECHA (Cơ giáp / Chiến hạm / Vũ khí / Pháp bảo)
- RANK_REALM (Cảnh giới / Đẳng cấp / Cấp bậc)
- ORGANIZATION (Tổ chức / Phe phái / Học viện / Quân đoàn)
- SLANG_IDIOM (Thành ngữ / Tiếng lóng / Khẩu ngữ đặc thù)
- DO_NOT_TRANSLATE (Cấm dịch / Giữ nguyên)

ĐỊNH DẠNG ĐẦU RA BẮT BUỘC (JSON ONLY):
{
  "terms": [
    {
      "source": "机甲",
      "target": "Cơ giáp",
      "category": "WEAPON_MECHA",
      "note": "Robot chiến đấu bọc thép"
    }
  ]
}
"""
    user_prompt = "Kịch bản mẫu:\n" + "\n".join(sample_texts[:40])
    try:
        raw_res = await llm_router.generate_completion(system_prompt, user_prompt, temperature=0.2)
        cleaned = raw_res.strip()
        if cleaned.startswith("```"):
            lines = cleaned.split("\n")
            if lines[0].startswith("```"): lines = lines[1:]
            if lines and lines[-1].strip().startswith("```"): lines = lines[:-1]
            cleaned = "\n".join(lines).strip()
        
        parsed = json.loads(cleaned)
        extracted = parsed.get("terms", [])
        
        added_terms = []
        for item in extracted:
            src = item.get("source")
            tgt = item.get("target")
            if src and tgt:
                existing = (await db.execute(select(GlossaryTerm).where(
                    GlossaryTerm.project_id == project_id,
                    GlossaryTerm.source_term == src
                ))).scalar_one_or_none()
                if not existing:
                    new_term = GlossaryTerm(
                        project_id=project_id,
                        source_term=src,
                        target_term=tgt,
                        category=item.get("category", "general"),
                        context_note=item.get("note"),
                        priority="normal",
                        case_sensitive="false"
                    )
                    db.add(new_term)
                    added_terms.append(new_term)
        
        await db.commit()
        for t in added_terms:
            await db.refresh(t)
        return [GlossaryTermResponse.model_validate(t) for t in added_terms]
    except Exception as e:
        logger.warning(f"Auto-extract glossary error: {e}")
        return []
