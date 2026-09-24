from typing import Optional, List, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field


class GlossaryTermCreate(BaseModel):
    source_term: str = Field(..., min_length=1, max_length=255)
    target_term: str = Field(..., min_length=1, max_length=255)
    category: str = "general" # PROPER_NAME, LOCATION, WEAPON_MECHA, RANK_REALM, ORGANIZATION, SLANG_IDIOM, DO_NOT_TRANSLATE
    context_note: Optional[str] = None
    priority: Optional[str] = "normal" # normal, high
    case_sensitive: Optional[str] = "false" # true, false


class GlossaryTermUpdate(BaseModel):
    source_term: Optional[str] = None
    target_term: Optional[str] = None
    category: Optional[str] = None
    context_note: Optional[str] = None
    priority: Optional[str] = None
    case_sensitive: Optional[str] = None


class GlossaryTermResponse(BaseModel):
    id: str
    project_id: str
    source_term: str
    target_term: str
    category: str
    context_note: Optional[str] = None
    priority: Optional[str] = "normal"
    case_sensitive: Optional[str] = "false"
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class GlossaryListResponse(BaseModel):
    project_id: str
    total: int
    items: List[GlossaryTermResponse]


class ApplyGlossaryPresetRequest(BaseModel):
    preset_key: str = Field(..., description="Preset ID, e.g. sci_fi_mecha, xianxia_cultivation")
    override_existing: bool = False


class GlossaryImportRequest(BaseModel):
    terms: List[GlossaryTermCreate]
    override_existing: bool = False


class GenrePresetSummary(BaseModel):
    id: str
    name: str
    icon: str
    genre: str
    description: str
    term_count: int
    speaker_count: int
