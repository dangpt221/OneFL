"""Application startup, durable dispatch and authorization in an isolated DB."""
import time
import asyncio
import pytest
from fastapi.testclient import TestClient
from app.config import settings


@pytest.fixture(autouse=True)
def runtime_database(tmp_path, monkeypatch):
    """API + worker need independent connections, unlike SQLite's one-connection :memory: pool."""
    import app.database as database
    from sqlalchemy import event
    from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
    from app.services.storage_service import storage_service
    engine = create_async_engine(f'sqlite+aiosqlite:///{tmp_path / "runtime.db"}')
    @event.listens_for(engine.sync_engine, 'connect')
    def configure(connection, _):
        cursor = connection.cursor()
        cursor.execute('PRAGMA foreign_keys=ON')
        cursor.execute('PRAGMA busy_timeout=30000')
        cursor.close()
    monkeypatch.setattr(database, 'engine', engine)
    monkeypatch.setattr(database, 'AsyncSessionLocal', async_sessionmaker(engine, expire_on_commit=False, autoflush=False))
    for key, leaf in [('OUTPUT_DIR', 'outputs'), ('UPLOAD_DIR', 'uploads'), ('TEMP_SCRATCH_DIR', 'scratch')]:
        path = tmp_path / leaf
        path.mkdir()
        monkeypatch.setattr(settings, key, path)
    monkeypatch.setattr(storage_service, 'output_dir', settings.OUTPUT_DIR)
    monkeypatch.setattr(storage_service, 'scratch_dir', settings.TEMP_SCRATCH_DIR)
    yield
    asyncio.run(engine.dispose())


def test_lifespan_dispatches_failure_and_keeps_it_visible(monkeypatch):
    from app.main import app
    from app.services.job_service import job_service
    token = 'runtime-regression-access-token-2026'
    monkeypatch.setattr(settings, 'API_ACCESS_TOKEN', token)
    monkeypatch.setattr(settings, 'AUTH_USERS', {})
    monkeypatch.setattr(settings, 'STORAGE_DRIVER', 'local')
    with TestClient(app) as client:
        assert client.get('/api/v1/health').status_code == 200
        assert client.get('/api/v1/projects').status_code == 401
        assert client.post('/api/v1/auth/login', json={'token': token}).status_code == 200
        response = client.post('/api/v1/projects', json={'title': 'runtime failure without media'})
        assert response.status_code == 201
        project_id = response.json()['id']
        queued = client.post(f'/api/v1/projects/{project_id}/pipeline/trigger', json={})
        assert queued.status_code == 200
        job_id = queued.json()['job_id']
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline:
            job = client.get(f'/api/v1/projects/{project_id}/jobs/{job_id}').json()
            if job['status'] == 'FAILED':
                break
            time.sleep(.1)
        assert job['status'] == 'FAILED'
        project = client.get(f'/api/v1/projects/{project_id}').json()
        assert project['status'] == 'FAILED' and 'missing' in project['error_message'].lower()
    assert job_service.runner is None


def test_two_users_cannot_access_each_others_projects(monkeypatch):
    from app.main import app
    monkeypatch.setattr(settings, 'API_ACCESS_TOKEN', None)
    monkeypatch.setattr(settings, 'AUTH_USERS', {'alice': 'alice-runtime-token-abcdefghijklmnopqrstuvwxyz', 'bob': 'bob-runtime-token-abcdefghijklmnopqrstuvwxyz'})
    monkeypatch.setattr(settings, 'STORAGE_DRIVER', 'local')
    with TestClient(app) as client:
        alice = {'Authorization': 'Bearer ' + settings.AUTH_USERS['alice']}
        bob = {'Authorization': 'Bearer ' + settings.AUTH_USERS['bob']}
        response = client.post('/api/v1/projects', json={'title': 'Alice private video'}, headers=alice)
        assert response.status_code == 201
        pid = response.json()['id']
        assert client.get(f'/api/v1/projects/{pid}', headers=bob).status_code == 404
        assert all(item['id'] != pid for item in client.get('/api/v1/projects', headers=bob).json()['items'])


def test_cleanup_preflight_never_queues_without_models(monkeypatch):
    from app.main import app
    import app.services.cleanup_ocr as ocr
    monkeypatch.setattr(settings, 'API_ACCESS_TOKEN', 'cleanup-runtime-token-abcdefghijklmnopqrstuvwxyz')
    monkeypatch.setattr(settings, 'AUTH_USERS', {})
    def unavailable(automatic):
        raise RuntimeError('Run scripts/prepare_video_cleanup.py')
    monkeypatch.setattr(ocr, 'check_cleanup_available', unavailable)
    with TestClient(app) as client:
        client.post('/api/v1/auth/login', json={'token': settings.API_ACCESS_TOKEN})
        pid = client.post('/api/v1/projects', json={'title': 'cleanup preflight'}).json()['id']
        response = client.post(f'/api/v1/projects/{pid}/pipeline/burn', json={'clean_chinese_mode': 'inpaint'})
        assert response.status_code == 422 and 'prepare_video_cleanup' in response.json()['detail']
        assert client.get(f'/api/v1/projects/{pid}').json()['active_job_id'] is None
        bad = client.post(f'/api/v1/projects/{pid}/pipeline/burn', json={
            'clean_chinese_mode': 'inpaint', 'cleanup_options': {'auto_detect_chinese': False, 'regions': []}})
        assert bad.status_code == 422


def test_cleanup_report_uses_current_output_and_owner(monkeypatch):
    from app.main import app
    from app.database import get_async_session
    from app.models.project import Project
    monkeypatch.setattr(settings, 'API_ACCESS_TOKEN', None)
    monkeypatch.setattr(settings, 'AUTH_USERS', {'alice': 'alice-cleanup-token-abcdefghijklmnopqrstuvwxyz', 'bob': 'bob-cleanup-token-abcdefghijklmnopqrstuvwxyz'})
    with TestClient(app) as client:
        alice = {'Authorization': 'Bearer ' + settings.AUTH_USERS['alice']}
        bob = {'Authorization': 'Bearer ' + settings.AUTH_USERS['bob']}
        pid = client.post('/api/v1/projects', json={'title': 'cleanup report'}, headers=alice).json()['id']
        url = f'/api/v1/projects/{pid}/pipeline/cleanup-report'
        assert client.get(url, headers=alice).status_code == 404
        async def attach():
            async with get_async_session() as db:
                project = await db.get(Project, pid)
                path = settings.OUTPUT_DIR / pid / 'output.mp4'
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(b'fixture output reference')
                path.with_suffix('.cleanup.json').write_text('{"processed_frames": 30, "masked_frames": 20, "ocr_scans": 4, "chinese_detections": 2, "tracking_misses": 1, "max_mask_ratio": 0.1, "processing_seconds": 1.2, "requires_review": true}')
                project.burned_video_path = str(path)
                await db.commit()
        client.portal.call(attach)
        assert client.get(url, headers=alice).json()['tracking_misses'] == 1
        assert client.get(url, headers=bob).status_code == 404


def test_failed_url_download_retries_download_and_releases_job(monkeypatch):
    from app.main import app
    from app.services.video_downloader import video_downloader, VideoDownloadError
    monkeypatch.setattr(settings, 'API_ACCESS_TOKEN', 'url-runtime-regression-access-token-2026')
    monkeypatch.setattr(settings, 'AUTH_USERS', {})
    calls = []
    async def unavailable(url, output_dir, progress_callback=None):
        calls.append(url)
        raise VideoDownloadError('BILIBILI_ACCESS_RESTRICTED', 'Bilibili từ chối truy cập; tải file video lên từ máy tính.')
    monkeypatch.setattr(video_downloader, 'download_video', unavailable)
    def wait_failed(client, project_id, job_id):
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline:
            job = client.get(f'/api/v1/projects/{project_id}/jobs/{job_id}').json()
            if job['status'] == 'FAILED':
                return job
            time.sleep(.05)
        raise AssertionError('Download did not terminate')
    with TestClient(app) as client:
        client.post('/api/v1/auth/login', json={'token': settings.API_ACCESS_TOKEN})
        response = client.post('/api/v1/projects/from-url', json={
            'url': 'https://www.bilibili.com/video/BV1MHh66uEFH/', 'auto_start_pipeline': False})
        assert response.status_code == 201
        pid, job_id = response.json()['id'], response.json()['active_job_id']
        assert wait_failed(client, pid, job_id)['kind'] == 'DOWNLOAD'
        failed = client.get(f'/api/v1/projects/{pid}').json()
        assert failed['status'] == 'FAILED' and failed['active_job_id'] is None
        assert 'tải file' in failed['error_message']
        retry = client.post(f'/api/v1/projects/{pid}/pipeline/trigger', json={'force_reprocess': True})
        assert retry.status_code == 200
        assert wait_failed(client, pid, retry.json()['job_id'])['kind'] == 'DOWNLOAD'
        assert len(calls) == 2
        assert client.get(f'/api/v1/projects/{pid}').json()['active_job_id'] is None
