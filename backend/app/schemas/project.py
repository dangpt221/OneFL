from typing import Optional, List, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field


class ProjectCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    source_language: str = "auto"
    target_language: str = "vi"
    settings_override: Optional[Dict[str, Any]] = None


class ProjectUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    source_language: Optional[str] = None
    target_language: Optional[str] = None
    status: Optional[str] = None
    default_voice: Optional[str] = None
    progress_percentage: Optional[int] = None
    settings_override: Optional[Dict[str, Any]] = None


class VideoChunkResponse(BaseModel):
    id: str
    chunk_index: int
    start_time: float
    end_time: float
    status: str
    audio_chunk_path: Optional[str] = None
    burned_chunk_path: Optional[str] = None

    class Config:
        from_attributes = True


class ProjectResponse(BaseModel):
    id: str
    title: str
    description: Optional[str] = None
    original_video_url: Optional[str] = None
    local_video_path: Optional[str] = None
    burned_video_url: Optional[str] = None
    dubbed_video_url: Optional[str] = None
    dubbed_audio_url: Optional[str] = None
    default_voice: Optional[str] = "nova"
    subtitles_ass_path: Optional[str] = None
    subtitles_srt_path: Optional[str] = None
    
    video_duration_seconds: Optional[float] = 0.0
    source_language: str
    target_language: str
    
    status: str
    current_stage: str
    progress_percentage: int
    error_message: Optional[str] = None
    settings_override: Optional[Dict[str, Any]] = None
    
    cue_count: Optional[int] = 0
    speaker_count: Optional[int] = 0
    glossary_count: Optional[int] = 0
    
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class ProjectListResponse(BaseModel):
    total: int
    items: List[ProjectResponse]
