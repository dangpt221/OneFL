from unittest.mock import AsyncMock
import httpx
import pytest
from app.config import settings
from tests.test_reliability import isolated_db


@pytest.mark.asyncio
async def test_api_requires_credentials_and_session_login_works(isolated_db, monkeypatch):
    from app.main import app
    from app.database import get_db
    monkeypatch.setattr(settings, 'API_ACCESS_TOKEN', 'test-token-for-local-security-audit')
    async def db_override():
        yield isolated_db
    app.dependency_overrides[get_db] = db_override
    try:
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url='http://localhost') as client:
            response = await client.get('/api/v1/projects')
            assert response.status_code == 401
            response = await client.post('/api/v1/auth/login', json={'token': settings.API_ACCESS_TOKEN})
            assert response.status_code == 200
            response = await client.get('/api/v1/projects')
            assert response.status_code == 200
            response = await client.post('/api/v1/projects', json={'title': 'secure'}, headers={'origin': 'https://untrusted.example'})
            assert response.status_code == 403
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
@pytest.mark.parametrize('url', ['http://127.0.0.1/video', 'http://169.254.169.254/latest', 'file:///tmp/video', 'https://youtube.com.evil.example/video'])
async def test_url_ingestion_rejects_internal_and_unapproved_hosts(url):
    from app.services.url_security import validate_video_url
    with pytest.raises(ValueError):
        await validate_video_url(url)
