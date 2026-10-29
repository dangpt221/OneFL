from typing import Optional, List, Dict, Any, Literal
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
    temperature: Optional[float] = Field(None, ge=0, le=2, allow_inf_nan=False)


class GuardrailCheckResult(BaseModel):
    passed: bool
    violations: List[Dict[str, Any]] = []
    fixed_subtitles: Optional[List[TranslationItemOutput]] = None


class PipelineTriggerRequest(BaseModel):
    stage: Optional[Literal['INGESTING', 'ASR_PROCESSING', 'SPEAKER_PROFILING', 'TRANSLATING']] = None
    burn_preset: Optional[str] = "p4"
    force_reprocess: bool = False


class BurnOptionsRequest(BaseModel):
    subtitle_preset: Literal['box_banner', 'cinema', 'yellow_highlight'] = 'box_banner'
    bilingual: bool = False
    mask_original_sub: bool = True
    clean_chinese_mode: Literal['cinema_bars', 'bottom_bar', 'smart_blur', 'cinema_zoom', 'none'] = 'cinema_bars'
    top_mask_pct: float = Field(11.0, ge=0, le=28, allow_inf_nan=False)
    bottom_mask_pct: float = Field(15.0, ge=0, le=35, allow_inf_nan=False)


class PipelineStatusResponse(BaseModel):
    project_id: str
    status: str
    current_stage: str
    progress_percentage: int
    error_message: Optional[str] = None
    active_workers: int = 0
    estimated_time_remaining_seconds: Optional[int] = None

