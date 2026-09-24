from typing import Optional, List, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field


class SpeakerProfileCreate(BaseModel):
    speaker_tag: str = Field(..., description="e.g. SPEAKER_00, NARRATOR")
    display_name: Optional[str] = None
    original_name: Optional[str] = None
    aliases: Optional[str] = None
    avatar_color: Optional[str] = "#6366f1"
    gender: str = "unknown"  # male, female, neutral, unknown
    age_group: str = "adult" # child, teen, young_adult, adult, senior, immortal
    role: Optional[str] = None
    tone: Optional[str] = None
    tts_voice: Optional[str] = "vi-VN-HoaiMyNeural"
    tts_speed: Optional[float] = 1.0
    notes: Optional[str] = None


class SpeakerProfileUpdate(BaseModel):
    display_name: Optional[str] = None
    original_name: Optional[str] = None
    aliases: Optional[str] = None
    avatar_color: Optional[str] = None
    gender: Optional[str] = None
    age_group: Optional[str] = None
    role: Optional[str] = None
    tone: Optional[str] = None
    tts_voice: Optional[str] = None
    tts_speed: Optional[float] = None
    notes: Optional[str] = None


class SpeakerProfileResponse(BaseModel):
    id: str
    project_id: str
    speaker_tag: str
    display_name: Optional[str] = None
    original_name: Optional[str] = None
    aliases: Optional[str] = None
    avatar_color: Optional[str] = "#6366f1"
    gender: str
    age_group: str
    role: Optional[str] = None
    tone: Optional[str] = None
    tts_voice: Optional[str] = "vi-VN-HoaiMyNeural"
    tts_speed: Optional[float] = 1.0
    notes: Optional[str] = None
    dialogue_count: Optional[int] = 0
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class RelationshipMatrixCreate(BaseModel):
    source_speaker: str
    target_speaker: str
    self_pronoun: str
    target_pronoun: str
    relationship_type: Optional[str] = None
    honorific_notes: Optional[str] = None


class RelationshipMatrixUpdate(BaseModel):
    self_pronoun: Optional[str] = None
    target_pronoun: Optional[str] = None
    relationship_type: Optional[str] = None
    honorific_notes: Optional[str] = None


class RelationshipMatrixResponse(BaseModel):
    id: str
    project_id: str
    source_speaker: str
    target_speaker: str
    self_pronoun: str
    target_pronoun: str
    relationship_type: Optional[str] = None
    honorific_notes: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class SpeakerMatrixFullResponse(BaseModel):
    speakers: List[SpeakerProfileResponse]
    relationships: List[RelationshipMatrixResponse]


class ApplySpeakerPresetRequest(BaseModel):
    preset_key: str = Field(..., description="Preset ID, e.g. sci_fi_mecha, xianxia_cultivation")
    override_existing: bool = False


class SpeakerImportRequest(BaseModel):
    speakers: Optional[List[SpeakerProfileCreate]] = []
    relationships: Optional[List[RelationshipMatrixCreate]] = []
    override_existing: bool = False
