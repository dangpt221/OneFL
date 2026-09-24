import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.config import settings
from app.database import init_db
from app.api.v1.projects import router as projects_router
from app.api.v1.subtitles import router as subtitles_router
from app.api.v1.speakers import router as speakers_router
from app.api.v1.glossary import router as glossary_router
from app.api.v1.pipeline import router as pipeline_router
from app.api.v1.tts import router as tts_router
from app.api.v1.settings import router as settings_router
from app.api.v1.websocket import router as ws_router

# Configure logging
logging.basicConfig(
    level=logging.INFO if not settings.DEBUG else logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
# Suppress high-frequency low-level debug spam
logging.getLogger("aiosqlite").setLevel(logging.WARNING)
logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
logging.getLogger("asyncio").setLevel(logging.WARNING)
logger = logging.getLogger("onefl")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Initializing OneFl Database and System Directories...")
    settings.ensure_directories()
    await init_db()
    from app.services.db_migrator import run_migrations
    run_migrations()
    logger.info("OneFl Backend initialized successfully.")
    yield
    logger.info("OneFl Backend shutting down...")


app = FastAPI(
    title=settings.APP_NAME,
    description="Auto Video Translation & Subtitle Burner System (Up to 10h Video Processing with Multi-LLM & Guardrails)",
    version="1.0.0",
    lifespan=lifespan
)

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files for media playback (data/ directory)
data_dir = settings.ROOT_DIR / "data"
data_dir.mkdir(parents=True, exist_ok=True)
app.mount("/static/data", StaticFiles(directory=str(data_dir)), name="static_data")

# Register V1 API Routes
app.include_router(projects_router, prefix=settings.API_V1_PREFIX)
app.include_router(subtitles_router, prefix=settings.API_V1_PREFIX)
app.include_router(speakers_router, prefix=settings.API_V1_PREFIX)
app.include_router(glossary_router, prefix=settings.API_V1_PREFIX)
app.include_router(pipeline_router, prefix=settings.API_V1_PREFIX)
app.include_router(tts_router, prefix=settings.API_V1_PREFIX)
app.include_router(settings_router, prefix=settings.API_V1_PREFIX)
app.include_router(ws_router, prefix=settings.API_V1_PREFIX)


@app.get("/")
async def root():
    return {
        "app": settings.APP_NAME,
        "version": "1.0.0",
        "status": "online",
        "docs_url": "/docs"
    }


@app.get("/health")
@app.get(f"{settings.API_V1_PREFIX}/health")
async def health():
    return {"status": "healthy"}
