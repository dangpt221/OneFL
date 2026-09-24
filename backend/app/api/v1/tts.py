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

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/tts", tags=["TTS & AI Dubbing"])


class TTSPreviewRequest(BaseModel):
    voice: str = Field("nova", description="Voice ID (e.g. nova, shimmer, alloy, onyx)")
    speed: float = Field(1.0, ge=0.5, le=2.0)
    sample_text: Optional[str] = None


class TTSPreviewResponse(BaseModel):
    voice_id: str
    name: str
    speed: float
    preview_url: str
    sample_text: str


class ProjectDubRequest(BaseModel):
    voice: str = Field("nova", description="Default project voice (default: nova for movie reviews)")
    model: str = Field("tts-1", description="OpenAI TTS model: tts-1 or tts-1-hd")
    speed: float = Field(1.0, ge=0.5, le=2.0)
    ducking_volume: float = Field(0.18, ge=0.0, le=1.0, description="Background music volume in Review Phim mode")
    mix_original: bool = Field(True, description="True for Review Phim / Recap mode (keep 18% BGM), False for complete audio replacement")
    speaker_voice_map: Optional[Dict[str, str]] = None


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
        custom_text=data.sample_text
    )
    return TTSPreviewResponse(**res)


async def _run_dubbing_task(
    project_id: str,
    voice: str,
    model: str,
    speed: float,
    ducking_volume: float,
    mix_original: bool,
    speaker_voice_map: Dict[str, str]
):
    """Background task orchestrating full video dubbing."""
    async with get_async_session() as db:
        res = await db.execute(select(Project).where(Project.id == project_id))
        project = res.scalar_one_or_none()
        if not project:
            return

        try:
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

            # If no custom speaker map provided, use the chosen single voice for all speakers
            if not speaker_voice_map:
                speaker_voice_map = {}

            cues_data = [
                {
                    "cue_index": c.cue_index,
                    "start_time": c.start_time,
                    "end_time": c.end_time,
                    "original_text": c.original_text,
                    "translated_text": c.translated_text or "",
                    "speaker_tag": c.speaker_tag
                }
                for c in cues
            ]

            # Progress callback for speech synthesis and audio mixing
            async def progress_cb(done_count: int, total_count: int, is_mixing: bool = False):
                if not is_mixing:
                    pct = int((done_count / total_count) * 100) if total_count > 0 else 0
                    progress_val = min(75, 15 + int((done_count / total_count) * 60))
                    msg = f"Đang tạo giọng nói cho phụ đề ({done_count}/{total_count} câu - {pct}%)..."
                else:
                    mix_pct = int((done_count / total_count) * 100) if total_count > 0 else 0
                    progress_val = min(95, 75 + int((done_count / total_count) * 20))
                    msg = f"Đang đồng bộ timeline & hòa trộn âm thanh ({done_count}/{total_count} đoạn - {mix_pct}%)..."

                try:
                    project.progress_percentage = progress_val
                    project.error_message = msg
                    await db.commit()
                except Exception:
                    pass

                await ws_manager.broadcast_to_project(project_id, "PROGRESS_UPDATE", {
                    "stage": "DUBBING_VOICE_SYNTHESIS" if not is_mixing else "DUBBING_VIDEO_MIXING",
                    "progress": progress_val,
                    "percentage": progress_val,
                    "message": msg,
                    "done_count": done_count,
                    "total_count": total_count
                })

            # 3. Dub Audio Timeline
            output_audio_path = settings.OUTPUT_DIR / f"{project_id}_dubbed.mp3"
            await tts_service.dub_project_timeline(
                cues_data=cues_data,
                total_duration=project.video_duration_seconds or 30.0,
                output_audio_path=output_audio_path,
                default_voice=voice,
                model=model,
                default_speed=speed,
                speaker_voice_map=speaker_voice_map,
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
            output_video_path = settings.OUTPUT_DIR / f"{project_id}_dubbed.mp4"

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

            if project.burned_video_url:
                project.status = "COMPLETED"
                project.current_stage = "COMPLETED"
                project.progress_percentage = 100
            else:
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
            logger.error(f"Dubbing failed for project {project_id}: {e}", exc_info=True)
            project.status = "FAILED"
            project.error_message = f"Dubbing error: {str(e)}"
            await db.commit()

            await ws_manager.broadcast_to_project(project_id, {
                "event": "pipeline_failed",
                "status": "FAILED",
                "error": str(e)
            })


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

    background_tasks.add_task(
        _run_dubbing_task,
        project_id=project_id,
        voice=data.voice,
        model=data.model,
        speed=data.speed,
        ducking_volume=data.ducking_volume,
        mix_original=data.mix_original,
        speaker_voice_map=data.speaker_voice_map or {}
    )

    return {
        "success": True,
        "message": f"AI Dubbing started with voice '{data.voice}'",
        "project_id": project_id,
        "status": "DUBBING"
    }


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
