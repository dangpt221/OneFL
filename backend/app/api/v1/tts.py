import logging
from typing import Optional, Dict, Any, List
from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, Body
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import get_db, get_async_session
from app.config import settings
from app.models.project import Project
from app.models.subtitle import SubtitleCue
from app.models.speaker import SpeakerProfile
from app.services.tts_service import tts_service, VOICE_CATALOG
from app.services.storage_service import storage_service
from app.services.ws_manager import ws_manager
from app.services.job_service import job_service
from app.services.artifact_service import invalidate_artifacts
from app.services.media_process import probe_media
from app.schemas.tts import ProjectDubRequest, DubbingTimingReport
from sqlalchemy import update
import uuid

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/tts", tags=["TTS & AI Dubbing"])


@router.get('/projects/{project_id}/timing', response_model=DubbingTimingReport)
async def get_project_timing_report(project_id: str, db: AsyncSession = Depends(get_db)) -> DubbingTimingReport:
    """Read timing measurements only for the currently referenced owned audio."""
    import asyncio
    from pydantic import ValidationError
    from app.security import current_user
    project = await db.get(Project, project_id)
    if not project or project.user_id != current_user.get() or not project.dubbed_audio_path:
        raise HTTPException(404, 'Current dubbing timing report not found')
    audio = Path(project.dubbed_audio_path).resolve()
    root = (settings.OUTPUT_DIR / project_id).resolve()
    report_path = audio.with_suffix('.timing.json')
    if not audio.is_relative_to(root) or not report_path.resolve().is_relative_to(root) or not audio.is_file():
        raise HTTPException(404, 'Current dubbing timing report not found')
    try:
        raw = await asyncio.to_thread(report_path.read_text, encoding='utf-8')
        return DubbingTimingReport.model_validate_json(raw)
    except FileNotFoundError:
        raise HTTPException(404, 'Regenerate dubbing to create its timing report')
    except (OSError, UnicodeError, ValidationError) as error:
        logger.exception('Cannot read dubbing timing report for %s', project_id)
        raise HTTPException(500, 'Dubbing timing report is invalid; regenerate dubbing') from error


class TTSPreviewRequest(BaseModel):
    voice: str = Field("vi-VN-HoaiMyNeural", description="Voice ID (e.g. vi-VN-HoaiMyNeural, vieneu-thuy-dung, vieneu-ngoc-huyen)")
    speed: float = Field(1.0, ge=0.5, le=2.0)
    sample_text: Optional[str] = Field(None, min_length=1, max_length=1000)
    model: Optional[str] = Field(None, min_length=1, max_length=100)


class TTSPreviewResponse(BaseModel):
    voice_id: str
    name: str
    speed: float
    preview_url: str
    sample_text: str


@router.get("/voices", response_model=List[Dict[str, Any]])
async def list_voices():
    """Retrieve all supported AI TTS voices, highlighting Nova for Film Review dubbing."""
    return tts_service.get_voices()


@router.post("/preview", response_model=TTSPreviewResponse)
async def preview_voice(data: TTSPreviewRequest):
    """Generate or retrieve a fast cached voice preview for real-time frontend playback."""
    res = await tts_service.generate_preview(
        voice=data.voice,
        speed=data.speed,
        custom_text=data.sample_text,
        model=data.model,
    )
    return TTSPreviewResponse(**res)


async def _run_dubbing_task(
    project_id: str,
    voice: str,
    model: str,
    speed: float,
    ducking_volume: float,
    mix_original: bool,
    speaker_voice_map: Optional[Dict[str, str]] = None,
    use_speaker_matrix: bool = False
):
    """Synthesize timed speech with the selected voices and publish current artifacts."""
    async with get_async_session() as db:
        res = await db.execute(select(Project).where(Project.id == project_id))
        project = res.scalar_one_or_none()
        if not project:
            return

        try:
            if not project.local_video_path:
                raise ValueError('Source video is missing')
            project.video_duration_seconds = await probe_media(Path(project.local_video_path), require_video=True)
            invalidate_artifacts(project, audio=True)
            # 1. Update Project State
            project.status = "DUBBING"
            project.current_stage = "DUBBING_VOICE_SYNTHESIS"
            project.progress_percentage = 15
            project.default_voice = voice
            project.dubbed_audio_path = None
            project.dubbed_audio_url = None
            project.dubbed_video_path = None
            project.dubbed_video_url = None
            project.error_message = f"Bắt đầu tổng hợp giọng lồng tiếng AI ({voice})..."
            await db.commit()

            await ws_manager.broadcast_to_project(project_id, "STAGE_CHANGED", {
                "stage": "DUBBING_VOICE_SYNTHESIS",
                "progress": 15,
                "percentage": 15,
                "message": f"Bắt đầu tổng hợp giọng lồng tiếng AI ({voice})..."
            })

            # 2. Fetch Cues & Speaker Map
            cues_res = await db.execute(
                select(SubtitleCue).where(SubtitleCue.project_id == project_id).order_by(SubtitleCue.cue_index)
            )
            cues = cues_res.scalars().all()

            if not cues:
                raise ValueError("Project has no subtitle cues to dub.")

            # If the user selected a voice in single-voice mode (use_speaker_matrix=False and no explicit speaker_voice_map),
            # ALL cues must strictly use `voice`.
            final_speaker_map = {}
            final_speed_map = {}
            if use_speaker_matrix and not speaker_voice_map:
                spk_res = await db.execute(
                    select(SpeakerProfile).where(SpeakerProfile.project_id == project_id)
                )
                db_speakers = spk_res.scalars().all()
                for s in db_speakers:
                    if s.speaker_tag and s.tts_voice:
                        final_speaker_map[s.speaker_tag] = s.tts_voice
                        final_speed_map[s.speaker_tag] = s.tts_speed or speed
            elif speaker_voice_map:
                final_speaker_map = dict(speaker_voice_map)


            cues_data = [
                {
                    "cue_index": c.cue_index,
                    "start_time": c.start_time,
                    "end_time": c.end_time,
                    "original_text": c.original_text,
                    "translated_text": c.translated_text,
                    "speaker_tag": c.speaker_tag
                }
                for c in cues
            ]

            # Progress callback for speech synthesis and audio mixing
            async def progress_cb(done_count: int, total_count: int, is_mixing: bool = False, cue_text: str = ""):
                if not is_mixing:
                    pct = int((done_count / total_count) * 100) if total_count > 0 else 0
                    progress_val = min(75, 15 + int((done_count / total_count) * 60))
                    msg = f"Đang tạo giọng nói cho phụ đề ({done_count}/{total_count} câu - {pct}%)..."
                else:
                    mix_pct = int((done_count / total_count) * 100) if total_count > 0 else 0
                    progress_val = min(95, 75 + int((done_count / total_count) * 20))
                    msg = f"Đang đồng bộ timeline & hòa trộn âm thanh ({done_count}/{total_count} đoạn - {mix_pct}%)..."

                if done_count % 15 == 0 or done_count == total_count:
                    project.progress_percentage = progress_val
                    project.error_message = msg
                    await db.commit()

                clean_text = (cue_text or "").replace("\n", " ").strip()
                if len(clean_text) > 60:
                    clean_text = clean_text[:57] + "..."

                await ws_manager.broadcast_to_project(project_id, "PROGRESS_UPDATE", {
                    "stage": "DUBBING_VOICE_SYNTHESIS" if not is_mixing else "DUBBING_VIDEO_MIXING",
                    "progress": progress_val,
                    "percentage": progress_val,
                    "message": msg,
                    "done_count": done_count,
                    "total_count": total_count,
                    "current_cue": clean_text
                })

            # 3. Dub Audio Timeline
            version = uuid.uuid4().hex
            output_audio_path = storage_service.get_project_dir(project_id) / f"dubbed_{version}.mp3"
            await tts_service.dub_project_timeline(
                cues_data=cues_data,
                total_duration=project.video_duration_seconds,
                output_audio_path=output_audio_path,
                default_voice=voice,
                model=model,
                default_speed=speed,
                speaker_voice_map=final_speaker_map,
                speaker_speed_map=final_speed_map,
                progress_callback=progress_cb
            )


            project.dubbed_audio_path = str(output_audio_path)
            project.dubbed_audio_url = storage_service.get_relative_url(output_audio_path)
            project.current_stage = "DUBBING_VIDEO_MIXING"
            project.progress_percentage = 75
            project.error_message = "Đang hòa trộn âm thanh lồng tiếng vào video gốc..."
            await db.commit()

            await ws_manager.broadcast_to_project(project_id, "STAGE_CHANGED", {
                "stage": "DUBBING_VIDEO_MIXING",
                "progress": 75,
                "percentage": 75,
                "message": "Đang hòa trộn âm thanh lồng tiếng vào video gốc..."
            })

            # 4. Mix with Video
            video_input = Path(project.local_video_path) if project.local_video_path else None
            output_video_path = storage_service.get_project_dir(project_id) / f"dubbed_{version}.mp4"

            if video_input and video_input.exists():
                await tts_service.mix_dubbed_video(
                    video_path=video_input,
                    dubbed_audio_path=output_audio_path,
                    output_video_path=output_video_path,
                    ducking_volume=ducking_volume,
                    mix_original=mix_original
                )
                project.dubbed_video_path = str(output_video_path)
                project.dubbed_video_url = storage_service.get_relative_url(output_video_path)

            project.status = "WAITING_REVIEW"
            project.current_stage = "WAITING_REVIEW"
            project.progress_percentage = 85
            project.error_message = "Hoàn tất lồng tiếng AI! Bạn có thể nghe thử video lồng tiếng và bấm 'Burn Video' để xuất bản sản phẩm hoàn chỉnh."
            await db.commit()

            await ws_manager.broadcast_to_project(project_id, "STATUS_UPDATE", {
                "status": project.status,
                "stage": project.current_stage,
                "current_stage": project.current_stage,
                "progress": project.progress_percentage,
                "dubbed_audio_url": project.dubbed_audio_url,
                "dubbed_video_url": project.dubbed_video_url,
                "message": project.error_message
            })

        except Exception as e:
            logger.exception('Dubbing failed for %s', project_id)
            await db.rollback()
            await db.execute(update(Project).where(Project.id == project_id).values(status='FAILED', error_message=str(e) or type(e).__name__))
            await db.commit()
            await ws_manager.broadcast_to_project(project_id, 'PIPELINE_ERROR', {'status': 'FAILED', 'error': str(e)})
            raise


@router.post("/projects/{project_id}/dub")
async def start_project_dubbing(
    project_id: str,
    background_tasks: BackgroundTasks,
    data: ProjectDubRequest = Body(...),
    db: AsyncSession = Depends(get_db)
):
    """Trigger automated AI dubbing with Nova/OpenAI or Edge voice for project subtitles."""
    res = await db.execute(select(Project).where(Project.id == project_id))
    project = res.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    config = data.model_dump()
    tts_service.get_voice_by_id(data.voice)
    for mapped_voice in (data.speaker_voice_map or {}).values():
        tts_service.get_voice_by_id(mapped_voice)
    job = await job_service.enqueue(db, project_id, 'DUBBING', config, project_updates={'last_dub_config': config, 'default_voice': data.voice})
    return {"success": True, "message": "AI dubbing queued", "project_id": project_id, "job_id": job.id, "status": "QUEUED"}


@router.get("/projects/{project_id}/dub")
async def get_project_dub_status(
    project_id: str,
    db: AsyncSession = Depends(get_db)
):
    """Get dubbing status and media URLs for project."""
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
