"""Access tokens and signed browser sessions; no credentials in media URLs."""
import base64
import binascii
import hashlib
import hmac
import ipaddress
import json
import re
import time
from collections import defaultdict, deque
from contextvars import ContextVar
from http.cookies import SimpleCookie
from urllib.parse import urlsplit

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, Field
from starlette.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.models.project import Project

current_user = ContextVar('onefl_user', default='local')
router = APIRouter(prefix='/auth', tags=['Authentication'])
_attempts = defaultdict(deque)
_heavy_requests = defaultdict(deque)


def credentials() -> dict[str, str]:
    users = dict(settings.AUTH_USERS)
    if settings.API_ACCESS_TOKEN:
        users['local'] = settings.API_ACCESS_TOKEN
    return users


def session_key() -> bytes:
    return hashlib.sha256((settings.SECRET_KEY + json.dumps(credentials(), sort_keys=True)).encode()).digest()


def make_session(user: str) -> str:
    payload = base64.urlsafe_b64encode(json.dumps([user, int(time.time()) + settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60]).encode()).decode()
    return payload + '.' + hmac.new(session_key(), payload.encode(), hashlib.sha256).hexdigest()


def read_session(cookie: str):
    try:
        payload, signature = cookie.rsplit('.', 1)
        expected = hmac.new(session_key(), payload.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(signature, expected):
            return None
        user, expires = json.loads(base64.urlsafe_b64decode(payload))
        if expires > time.time() and user in credentials():
            return user
    except (ValueError, TypeError, KeyError, binascii.Error, UnicodeError):
        return None


def authenticate(scope):
    headers = dict(scope.get('headers', []))
    token = headers.get(b'authorization', b'').decode().removeprefix('Bearer ')
    for user, expected in credentials().items():
        if token and hmac.compare_digest(token, expected):
            return user
    cookies = SimpleCookie()
    try:
        cookies.load(headers.get(b'cookie', b'').decode())
        if 'onefl_session' in cookies:
            user = read_session(cookies['onefl_session'].value)
            if user:
                return user
    except Exception:
        return None
    if not credentials() and settings.ENV != 'production':
        peer = (scope.get('client') or ('', 0))[0]
        host = urlsplit('//' + headers.get(b'host', b'').decode()).hostname
        # TestClient is an in-process development client. Real listeners still
        # require both a loopback peer and loopback host (DNS-rebinding defense).
        if peer == 'testclient' or (peer in {'127.0.0.1', '::1'} and host in {'localhost', '127.0.0.1', '::1'}):
            return 'local'
    return None


def valid_origin(scope) -> bool:
    headers = dict(scope.get('headers', []))
    origin = headers.get(b'origin', b'').decode()
    if not origin:
        return True  # CLI/Bearer requests do not use ambient browser credentials.
    allowed = {o.rstrip('/') for o in settings.CORS_ORIGINS if o != '*'}
    authority = headers.get(b'host', b'').decode()
    return origin.rstrip('/') in allowed or urlsplit(origin).netloc == authority


class AccessMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope['type'] not in {'http', 'websocket'}:
            return await self.app(scope, receive, send)
        path = scope.get('path', '')
        protected = path.startswith(('/api/', '/static/'))
        exempt = path in {'/api/v1/health', '/api/v1/auth/login', '/api/v1/auth/session'} or scope.get('method') == 'OPTIONS'
        user = authenticate(scope)
        denied = 403 if not valid_origin(scope) else 401 if protected and not exempt and not user else None
        if denied:
            if scope['type'] == 'websocket':
                return await send({'type': 'websocket.close', 'code': 4400 + denied % 100})
            return await JSONResponse({'detail': 'Origin not allowed' if denied == 403 else 'Authentication required'}, status_code=denied)(scope, receive, send)
        if scope.get('method') == 'POST' and path.endswith(('/preview', '/test-key', '/execute-tool', '/chat', '/url-info', '/from-url')):
            now = time.monotonic()
            bucket = _heavy_requests[user or (scope.get('client') or ('unknown',))[0]]
            while bucket and bucket[0] < now - 60:
                bucket.popleft()
            if len(bucket) >= 20:
                return await JSONResponse({'detail': 'Request quota reached; retry in one minute'}, status_code=429)(scope, receive, send)
            bucket.append(now)
        handle = current_user.set(user or 'local')
        scope.setdefault('state', {})['user_id'] = user
        try:
            await self.app(scope, receive, send)
        finally:
            current_user.reset(handle)


async def project_access(request: Request, db: AsyncSession = Depends(get_db)):
    project_id = request.path_params.get('project_id')
    if not project_id:
        return
    project = await db.get(Project, project_id)
    if not project or project.user_id != current_user.get():
        raise HTTPException(404, 'Project not found')
    if project.active_job_id and request.method in {'PATCH', 'DELETE', 'POST'}:
        path = request.url.path
        allowed = path.endswith(('/reset-status', '/resume-dubbing', '/dub', '/trigger', '/burn', '/retranslate', '/finalize')) or (request.method == 'DELETE' and path.endswith('/' + project_id))
        if not allowed:
            raise HTTPException(409, 'Cancel the active job before editing this project')


class LoginRequest(BaseModel):
    token: str = Field(min_length=1, max_length=512)


@router.post('/login')
async def login(data: LoginRequest, request: Request, response: Response):
    peer = request.client.host
    now = time.monotonic()
    if len(_attempts) > 10000:
        for key in list(_attempts):
            if not _attempts[key] or _attempts[key][-1] < now - 60:
                del _attempts[key]
    attempts = _attempts[peer]
    while attempts and attempts[0] < now - 60:
        attempts.popleft()
    if len(attempts) >= 10:
        raise HTTPException(429, 'Too many login attempts; retry in one minute')
    attempts.append(now)
    user = next((user for user, token in credentials().items() if hmac.compare_digest(data.token, token)), None)
    if user is None:
        raise HTTPException(401, 'Invalid access token')
    response.set_cookie('onefl_session', make_session(user), httponly=True, secure=settings.ENV == 'production', samesite='lax', max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60)
    return {'authenticated': True, 'user_id': user}


@router.get('/session')
async def session(request: Request):
    user = authenticate(request.scope)
    return {'authenticated': bool(user), 'user_id': user}


@router.post('/logout')
async def logout(response: Response):
    response.delete_cookie('onefl_session')
    return {'success': True}
