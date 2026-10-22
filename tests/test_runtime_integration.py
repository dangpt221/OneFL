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
