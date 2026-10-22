from typing import Optional, List
from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class SubtitleCueCreate(BaseModel):
    model_config = ConfigDict(allow_inf_nan=False)
    cue_index: int = Field(ge=1)
    start_time: float = Field(ge=0)
    end_time: float = Field(gt=0)
    original_text: str
    translated_text: Optional[str] = None
    speaker_tag: str = "SPEAKER_00"
    target_speaker_tag: Optional[str] = None

    @model_validator(mode='after')
    def ordered_times(self):
        if self.end_time <= self.start_time:
            raise ValueError('end_time must be greater than start_time')
        return self


class SubtitleCueUpdate(BaseModel):
    model_config = ConfigDict(allow_inf_nan=False)
    start_time: Optional[float] = Field(None, ge=0)
    end_time: Optional[float] = Field(None, gt=0)
    original_text: Optional[str] = None
    translated_text: Optional[str] = None
    speaker_tag: Optional[str] = None
    target_speaker_tag: Optional[str] = None
    is_edited: Optional[bool] = True

    @model_validator(mode='after')
    def valid_patch(self):
        for name in ('start_time', 'end_time', 'original_text', 'speaker_tag', 'is_edited'):
            if name in self.model_fields_set and getattr(self, name) is None:
                raise ValueError(f'{name} cannot be null')
        if self.start_time is not None and self.end_time is not None and self.end_time <= self.start_time:
            raise ValueError('end_time must be greater than start_time')
        return self


class BatchSubtitleUpdate(BaseModel):
    cues: List[SubtitleCueUpdate]


class SubtitleCueResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    project_id: str
    cue_index: int
    start_time: float
    end_time: float
    original_text: str
    translated_text: Optional[str] = None
    speaker_tag: str = "SPEAKER_00"
    target_speaker_tag: Optional[str] = None
    cps: float = 0.0
    line_count: int = 1
    max_line_length: int = 0
    has_guardrail_violation: bool = False
    violation_notes: Optional[str] = None
    is_edited: bool = False
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    @field_validator("cps", mode="before")
    @classmethod
    def val_cps(cls, v):
        return float(v) if v is not None else 0.0

    @field_validator("line_count", mode="before")
    @classmethod
    def val_line_count(cls, v):
        return int(v) if v is not None else 1

    @field_validator("max_line_length", mode="before")
    @classmethod
    def val_max_line_length(cls, v):
        return int(v) if v is not None else 0

    @field_validator("has_guardrail_violation", "is_edited", mode="before")
    @classmethod
    def val_bool(cls, v):
        return bool(v) if v is not None else False

    @field_validator("speaker_tag", mode="before")
    @classmethod
    def val_speaker_tag(cls, v):
        return v if v else "SPEAKER_00"

    @field_validator("created_at", "updated_at", mode="before")
    @classmethod
    def val_datetime(cls, v):
        return v if v is not None else datetime.now()


class SubtitleListResponse(BaseModel):
    project_id: str
    total_cues: int
    items: List[SubtitleCueResponse]

