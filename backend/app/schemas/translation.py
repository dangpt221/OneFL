from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field


class TranslationItemInput(BaseModel):
    id: int
    text: str
    speaker: str = "SPEAKER_00"
    target_speaker: Optional[str] = None
    duration: Optional[float] = None


class TranslationItemOutput(BaseModel):
    id: int
    text: str


class LLMTranslationResponse(BaseModel):
    translations: List[TranslationItemOutput]


class RetranslateRequest(BaseModel):
    cue_ids: List[str] = Field(..., description="List of SubtitleCue IDs to re-translate")
    model_override: Optional[str] = None
    custom_instruction: Optional[str] = None
    temperature: Optional[float] = None


class GuardrailCheckResult(BaseModel):
    passed: bool
    violations: List[Dict[str, Any]] = []
    fixed_subtitles: Optional[List[TranslationItemOutput]] = None


class PipelineTriggerRequest(BaseModel):
    stage: Optional[str] = None  # None for full pipeline, or specific stage
    burn_preset: Optional[str] = "p4"
    force_reprocess: bool = False


class BurnOptionsRequest(BaseModel):
    subtitle_preset: Optional[str] = Field("box_banner", description="Style preset: box_banner, cinema, yellow_highlight")
    bilingual: Optional[bool] = Field(False, description="Enable dual bilingual subtitles")
    mask_original_sub: Optional[bool] = Field(True, description="Conceal original foreign hardsubs")
    clean_chinese_mode: Optional[str] = Field("cinema_bars", description="Clean Chinese mode: cinema_bars, bottom_bar, smart_blur, cinema_zoom, none")
    top_mask_pct: Optional[float] = Field(11.0, description="Top mask height in percentage (e.g. 11.0 for 11%)")
    bottom_mask_pct: Optional[float] = Field(15.0, description="Bottom mask height in percentage (e.g. 15.0 for 15%)")


class PipelineStatusResponse(BaseModel):
    project_id: str
    status: str
    current_stage: str
    progress_percentage: int
    error_message: Optional[str] = None
    active_workers: int = 0
    estimated_time_remaining_seconds: Optional[int] = None

