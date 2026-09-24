import shutil
from pathlib import Path
from typing import Dict, Any, Optional
from pydantic import BaseModel
from fastapi import APIRouter
from app.config import settings
from app.services.llm_router import llm_router

router = APIRouter(prefix="/settings", tags=["System Settings & Diagnostics"])


class TestAPIKeyRequest(BaseModel):
    provider: str  # gemini | openai
    api_key: Optional[str] = None
    model: Optional[str] = None


@router.get("/info")
async def get_system_settings():
    """Retrieve system configuration and status."""
    has_gemini = bool(settings.GEMINI_API_KEY and "DIEN_API_KEY" not in settings.GEMINI_API_KEY)
    has_openai = bool(settings.OPENAI_API_KEY and "DIEN_API_KEY" not in settings.OPENAI_API_KEY)
    ffmpeg_bin = settings.get_ffmpeg_bin()
    has_ffmpeg = bool(shutil.which(ffmpeg_bin) or (ffmpeg_bin and Path(ffmpeg_bin).exists()))

    return {
        "app_name": settings.APP_NAME,
        "env": settings.ENV,
        "debug": settings.DEBUG,
        "primary_provider": settings.TRANSLATION_PRIMARY_PROVIDER,
        "fallback_provider": settings.TRANSLATION_FALLBACK_PROVIDER,
        "gemini_configured": has_gemini,
        "gemini_model": settings.GEMINI_MODEL,
        "openai_configured": has_openai,
        "openai_model": settings.OPENAI_MODEL,
        "ffmpeg_available": has_ffmpeg,
        "guardrails_enabled": settings.ENABLE_GUARDRAILS,
        "max_line_length": settings.MAX_SUBTITLE_LINE_LENGTH,
        "max_cps": settings.MAX_CPS,
        "storage_driver": settings.STORAGE_DRIVER
    }


@router.post("/test-key")
async def test_llm_key(req: TestAPIKeyRequest):
    """Test connectivity for Gemini or OpenAI API Key."""
    return await llm_router.test_connection(
        provider=req.provider,
        api_key=req.api_key,
        model=req.model
    )
