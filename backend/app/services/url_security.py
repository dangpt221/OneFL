"""Restrict user-supplied ingestion URLs before any provider request."""
import asyncio
import ipaddress
import socket
from urllib.parse import urlsplit
from app.config import settings


async def validate_video_url(url: str) -> None:
    parsed = urlsplit(url)
    host = (parsed.hostname or '').lower().rstrip('.')
    if parsed.scheme not in {'http', 'https'} or parsed.username or parsed.password or parsed.port not in (None, 80, 443):
        raise ValueError('Only public HTTP(S) video URLs are accepted')
    if not any(host == allowed or host.endswith('.' + allowed) for allowed in settings.ALLOWED_VIDEO_HOSTS):
        raise ValueError('Video host is not in ALLOWED_VIDEO_HOSTS')
    addresses = await asyncio.to_thread(socket.getaddrinfo, host, parsed.port or 443, type=socket.SOCK_STREAM)
    if not addresses or any(not ipaddress.ip_address(item[4][0]).is_global for item in addresses):
        raise ValueError('Video URL resolves to a private or reserved address')
