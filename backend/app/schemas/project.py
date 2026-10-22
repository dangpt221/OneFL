from typing import Optional, List, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field, ConfigDict, model_validator


class ProjectCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    source_language: str = "auto"
    target_language: str = "vi"
    settings_override: Optional[Dict[str, Any]] = None


class ProjectUpdate(BaseModel):
    model_config = ConfigDict(extra='forbid')
    title: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    source_language: Optional[str] = None
    target_language: Optional[str] = None
    default_voice: Optional[str] = None
    settings_override: Optional[Dict[str, Any]] = None

    @model_validator(mode='before')
    @classmethod
    def required_metadata(cls, values):
        for key in ('title', 'source_language', 'target_language', 'default_voice'):
            if key in values and (values[key] is None or not str(values[key]).strip()):
                raise ValueError(f'{key} cannot be empty')
        return values


class VideoChunkResponse(BaseModel):
    id: str
    chunk_index: int
    start_time: float
    end_time: float
    status: str
    audio_chunk_path: Optional[str] = None
    burned_chunk_path: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class ProjectResponse(BaseModel):
    id: str
    title: str
    content_revision: int = 0
    active_job_id: Optional[str] = None
    last_job_kind: Optional[str] = None
    last_dub_config: Optional[Dict[str, Any]] = None
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

    model_config = ConfigDict(from_attributes=True)


class ProjectListResponse(BaseModel):
    total: int
    items: List[ProjectResponse]
