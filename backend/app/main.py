import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends, Request
from fastapi.responses import JSONResponse
from app.security import AccessMiddleware, project_access, router as auth_router, credentials
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy.exc import IntegrityError
from app.services.private_media import PrivateMediaFiles
import sys
import asyncio

if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

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
from app.api.v1.agent import router as agent_router


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
    if settings.ENV == 'production' and not credentials():
        raise RuntimeError('Production requires API_ACCESS_TOKEN or AUTH_USERS')
    if any(len(token) < 24 for token in credentials().values()):
        raise RuntimeError('Access tokens must contain at least 24 characters')
    if settings.STORAGE_DRIVER != 'local':
        raise RuntimeError('Only local storage is implemented; use a mounted persistent volume')
    await init_db()
    from app.services.job_service import job_service
    await job_service.start()
    logger.info("OneFl Backend initialized successfully.")
    try:
        yield
    finally:
        await job_service.stop()
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
    allow_origins=[origin for origin in settings.CORS_ORIGINS if origin != "*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files for media playback (data/ directory)
data_dir = settings.ROOT_DIR / "data"
data_dir.mkdir(parents=True, exist_ok=True)
# Media roots may be configured outside the source tree.
app.mount('/static/data/outputs', PrivateMediaFiles(directory=str(settings.OUTPUT_DIR)), name='outputs')
app.mount('/static/data/uploads', PrivateMediaFiles(directory=str(settings.UPLOAD_DIR)), name='uploads')
app.add_middleware(AccessMiddleware)
app.include_router(auth_router, prefix=settings.API_V1_PREFIX)

@app.exception_handler(ValueError)
async def invalid_input(request: Request, error: ValueError):
    return JSONResponse({'detail': str(error)}, status_code=422)

@app.exception_handler(RuntimeError)
async def processing_error(request: Request, error: RuntimeError):
    logger.error('Request failed: %s', type(error).__name__, exc_info=error)
    return JSONResponse({'detail': 'Processing failed; see server logs or project status'}, status_code=502)


@app.exception_handler(IntegrityError)
async def conflicting_data(request: Request, error: IntegrityError):
    logger.warning('Database rejected a conflicting write on %s', request.url.path)
    return JSONResponse({'detail': 'Data conflict; refresh and check duplicate IDs or invalid values'}, status_code=409)

# Register V1 API Routes
app.include_router(projects_router, prefix=settings.API_V1_PREFIX, dependencies=[Depends(project_access)])
app.include_router(subtitles_router, prefix=settings.API_V1_PREFIX, dependencies=[Depends(project_access)])
app.include_router(speakers_router, prefix=settings.API_V1_PREFIX, dependencies=[Depends(project_access)])
app.include_router(glossary_router, prefix=settings.API_V1_PREFIX, dependencies=[Depends(project_access)])
app.include_router(pipeline_router, prefix=settings.API_V1_PREFIX, dependencies=[Depends(project_access)])
app.include_router(tts_router, prefix=settings.API_V1_PREFIX, dependencies=[Depends(project_access)])
app.include_router(settings_router, prefix=settings.API_V1_PREFIX, dependencies=[Depends(project_access)])
app.include_router(ws_router, prefix=settings.API_V1_PREFIX)
app.include_router(agent_router, prefix=settings.API_V1_PREFIX, dependencies=[Depends(project_access)])



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
    from sqlalchemy import text
    from app.database import get_async_session
    try:
        async with get_async_session() as db:
            await db.execute(text('SELECT 1'))
        if not settings.OUTPUT_DIR.is_dir() or not settings.TEMP_SCRATCH_DIR.is_dir():
            raise RuntimeError('Storage unavailable')
    except Exception:
        logger.exception('Readiness probe failed')
        return JSONResponse({'status': 'unhealthy'}, status_code=503)
    return {'status': 'healthy', 'database': 'ready', 'storage': 'ready'}
