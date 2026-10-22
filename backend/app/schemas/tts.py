"""Shared dubbing configuration for HTTP and Agent admission."""
from typing import Optional, Dict
from pydantic import BaseModel, ConfigDict, Field


class ProjectDubRequest(BaseModel):
    model_config = ConfigDict(allow_inf_nan=False)
    voice: str = Field('vi-VN-HoaiMyNeural', min_length=1, max_length=100)
    model: str = Field('tts-1', min_length=1, max_length=100)
    speed: float = Field(1.0, ge=0.5, le=2.0)
    ducking_volume: float = Field(0.18, ge=0, le=1)
    mix_original: bool = True
    speaker_voice_map: Optional[Dict[str, str]] = None
    use_speaker_matrix: bool = False


class CueTimingMeasurement(BaseModel):
    model_config = ConfigDict(allow_inf_nan=False)
    cue_index: int
    start_time: float = Field(ge=0)
    end_time: float = Field(gt=0)
    source_duration: float = Field(gt=0)
    fitted_duration: float = Field(gt=0)
    audio_end: float = Field(gt=0)
    speedup: float = Field(ge=1, le=2.5)
    overlaps: bool


class DubbingTimingReport(BaseModel):
    model_config = ConfigDict(allow_inf_nan=False)
    version: int = 1
    cue_count: int = Field(ge=0)
    overlap_cue_count: int = Field(ge=0)
    max_speedup: float = Field(ge=1, le=2.5)
    cues: list[CueTimingMeasurement]
