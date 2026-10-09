import os
from pathlib import Path
from typing import List, Optional
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field, model_validator

# Base Directory of Workspace (OneFl)
ROOT_DIR = Path(__file__).resolve().parent.parent.parent
ENV_PATH = ROOT_DIR / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(ENV_PATH) if ENV_PATH.exists() else None,
        env_file_encoding="utf-8",
        extra="ignore"
    )

    # 1. Application & Server
    ROOT_DIR: Path = ROOT_DIR
    ENV: str = "development"
    DEBUG: bool = True
    APP_NAME: str = "OneFl Video Translator"
    APP_HOST: str = "0.0.0.0"
    APP_PORT: int = 8000
    API_V1_PREFIX: str = "/api/v1"
    CORS_ORIGINS: List[str] = ["http://localhost:3000", "http://127.0.0.1:3000", "*"]
    SECRET_KEY: str = "onefl_super_secret_jwt_and_session_key_2026"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440

    # 2. Database
    DATABASE_URL: str = "sqlite+aiosqlite:///./onefl_videotrans.db"
    POSTGRES_HOST: Optional[str] = "localhost"
    POSTGRES_PORT: Optional[int] = 5432
    POSTGRES_USER: Optional[str] = "postgres"
    POSTGRES_PASSWORD: Optional[str] = "postgres"
    POSTGRES_DB: Optional[str] = "onefl_videotrans"

    # 3. Storage & Directories
    STORAGE_DRIVER: str = "local"  # local | s3 | r2 | minio
    UPLOAD_DIR: Path = ROOT_DIR / "data" / "uploads"
    OUTPUT_DIR: Path = ROOT_DIR / "data" / "outputs"
    TEMP_SCRATCH_DIR: Path = ROOT_DIR / "tmp" / "scratch"
    
    @model_validator(mode="after")
    def resolve_paths(self):
        if not self.UPLOAD_DIR.is_absolute():
            self.UPLOAD_DIR = (self.ROOT_DIR / self.UPLOAD_DIR).resolve()
        if not self.OUTPUT_DIR.is_absolute():
            self.OUTPUT_DIR = (self.ROOT_DIR / self.OUTPUT_DIR).resolve()
        if not self.TEMP_SCRATCH_DIR.is_absolute():
            self.TEMP_SCRATCH_DIR = (self.ROOT_DIR / self.TEMP_SCRATCH_DIR).resolve()
        return self

    # S3 / R2 / MinIO Optional Config
    S3_ENDPOINT_URL: Optional[str] = None
    S3_ACCESS_KEY_ID: Optional[str] = None
    S3_SECRET_ACCESS_KEY: Optional[str] = None
    S3_BUCKET_NAME: Optional[str] = "onefl-video-bucket"
    S3_REGION: Optional[str] = "us-east-1"
    S3_PRESIGNED_EXPIRY_SECONDS: int = 86400

    # 4. ASR & Diarization
    WHISPER_MODEL_SIZE: str = "tiny"
    WHISPER_DEVICE: str = "cpu"
    WHISPER_COMPUTE_TYPE: str = "int8"
    WHISPER_BEAM_SIZE: int = 5
    ASR_MAX_DURATION_SECONDS: Optional[int] = None
    ENABLE_SPEAKER_DIARIZATION: bool = True
    ENABLE_SPEAKER_PROFILER: bool = True
    HF_TOKEN: Optional[str] = None

    # 5. LLM Translation & Multi-Provider Router
    TRANSLATION_PRIMARY_PROVIDER: str = "gemini"  # gemini | openai | anthropic
    TRANSLATION_FALLBACK_PROVIDER: str = "openai"
    ENABLE_AUTO_FALLBACK_ON_ERROR: bool = True

    # Translation Parameters
    DEFAULT_SOURCE_LANGUAGE: str = "auto"
    DEFAULT_TARGET_LANGUAGE: str = "vi"
    LLM_BATCH_SIZE_LINES: int = 80
    LLM_CONTEXT_WINDOW_LINES: int = 5
    LLM_TEMPERATURE: float = 0.3
    LLM_TIMEOUT_SECONDS: int = 45
    LLM_ENABLE_JSON_MODE: bool = True

    # API Keys
    GEMINI_API_KEY: Optional[str] = None
    GEMINI_MODEL: str = "gemini-3.6-flash"
    GEMINI_MAX_CONCURRENCY: int = 10

    OPENAI_API_KEY: Optional[str] = None
    OPENAI_API_BASE: str = "https://api.openai.com/v1"
    OPENAI_MODEL: str = "gpt-4o-mini"
    OPENAI_MAX_CONCURRENCY: int = 10

    ANTHROPIC_API_KEY: Optional[str] = None
    ANTHROPIC_MODEL: str = "claude-3-5-sonnet-20241022"

    # 6. Guardrails & QC System
    ENABLE_GUARDRAILS: bool = True
    GUARDRAIL_MAX_REFLEXION_RETRIES: int = 2
    GUARDRAIL_CHECK_PRONOUN_CONSISTENCY: bool = True
    GUARDRAIL_STRICT_GLOSSARY: bool = True
    MAX_SUBTITLE_LINE_LENGTH: int = 40
    MAX_SUBTITLE_LINES: int = 2
    MAX_CPS: float = 20.0

    # Multi-language styles
    ZH_TRANSLATION_STYLE: str = "modern_vietnamese"  # modern_vietnamese | han_viet
    JA_KEIGO_SENSITIVITY: str = "high"
    KO_HONORIFIC_SENSITIVITY: str = "high"

    # 7. Video Chunking & Subtitle Styling
    FFMPEG_PATH: str = Field(default_factory=lambda: (
        __import__("shutil").which("ffmpeg") or 
        (getattr(__import__("imageio_ffmpeg", fromlist=["get_ffmpeg_exe"]), "get_ffmpeg_exe", lambda: "ffmpeg")())
    ))
    FFPROBE_PATH: str = "ffprobe"
    VIDEO_CHUNK_DURATION_SECONDS: int = 1200
    MAX_CONCURRENT_GPU_BURN_WORKERS: int = 8
    NVENC_GPU_DEVICE_ID: int = 0
    NVENC_PRESET: str = "p4"
    NVENC_CQ_LEVEL: int = 23
    BURN_OUTPUT_AUDIO_BITRATE: str = "192k"

    # 8. TTS Dubbing Engine
    DEFAULT_TTS_VOICE: str = "vi-VN-HoaiMyNeural"  # 🌸 Microsoft Hoài My Neural (Chuẩn tiếng Việt tự nhiên)
    DEFAULT_TTS_MODEL: str = "tts-1" # tts-1 | tts-1-hd
    DEFAULT_TTS_SPEED: float = 1.0
    DEFAULT_DUCKING_VOLUME: float = 0.18  # 18% background music volume
    DEFAULT_TTS_PROVIDER: str = "edge-tts"

    SUB_FONT_NAME: str = "Roboto"
    SUB_FONT_SIZE: int = 22
    SUB_PRIMARY_COLOR: str = "&H00FFFFFF"
    SUB_OUTLINE_COLOR: str = "&H00000000"
    SUB_OUTLINE_WIDTH: int = 2
    SUB_SHADOW_DEPTH: int = 1
    SUB_MARGIN_BOTTOM: int = 25

    def get_ffmpeg_bin(self) -> str:
        import shutil
        if shutil.which(self.FFMPEG_PATH):
            return self.FFMPEG_PATH
        try:
            import imageio_ffmpeg
            return imageio_ffmpeg.get_ffmpeg_exe()
        except Exception:
            return self.FFMPEG_PATH

    def ensure_directories(self):
        """Create necessary working directories if they do not exist."""
        self.UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
        self.OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        self.TEMP_SCRATCH_DIR.mkdir(parents=True, exist_ok=True)


settings = Settings()
settings.ensure_directories()
