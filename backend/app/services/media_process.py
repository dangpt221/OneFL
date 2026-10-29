"""Cancellable media processes with bounded diagnostic output."""

import asyncio
import re
import tempfile
from collections import OrderedDict
from weakref import WeakKeyDictionary, WeakValueDictionary
from pathlib import Path
from typing import Optional, Sequence

from app.config import settings

_probe_caches = WeakKeyDictionary()
_probe_locks = WeakKeyDictionary()
_PROBE_CACHE_SIZE = 512


async def run_media(
    args: Sequence[str], *, cwd: Optional[Path] = None,
    timeout: float = 7200, allowed_codes: tuple[int, ...] = (0,),
) -> tuple[bytes, bytes]:
    # FFmpeg progress/diagnostics may be large for a ten-hour input. Keep them on
    # disk instead of accumulating PIPE buffers in the API process.
    with tempfile.TemporaryFile() as stdout, tempfile.TemporaryFile() as stderr:
        process = await asyncio.create_subprocess_exec(
            *map(str, args), cwd=str(cwd) if cwd else None,
            stdout=stdout, stderr=stderr,
        )
        try:
            # communicate also drains mocked subprocesses in isolated tests.
            returned = await asyncio.wait_for(process.communicate(), timeout)
        except (asyncio.CancelledError, asyncio.TimeoutError):
            if process.returncode is None:
                process.kill()
                await process.wait()
            raise
        stdout.seek(0)
        out = stdout.read(1024 * 1024)
        stderr.seek(0, 2)
        stderr.seek(max(0, stderr.tell() - 16384))
        err = stderr.read()
        if returned:
            out = returned[0] or out
            err = returned[1] or err
        if process.returncode not in allowed_codes:
            raise RuntimeError(f"Media process failed ({process.returncode}): {err.decode(errors='replace')[-4000:]}")
        return out, err


async def probe_media(path: Path, *, require_video: bool = False, require_audio: bool = False) -> float:
    if not path.is_file() or path.stat().st_size == 0:
        raise FileNotFoundError(f"Media output is missing or empty: {path.name}")
    stat = path.stat()
    key = (str(path.resolve()), stat.st_size, stat.st_mtime_ns, stat.st_ctime_ns, stat.st_ino)
    loop = asyncio.get_running_loop()
    cache = _probe_caches.setdefault(loop, OrderedDict())
    locks = _probe_locks.setdefault(loop, WeakValueDictionary())
    lock = locks.get(key)
    if lock is None:
        lock = asyncio.Lock()
        locks[key] = lock
    async with lock:
        if key not in cache:
            _, err = await run_media(
                [settings.get_ffmpeg_bin(), '-hide_banner', '-i', str(path)],
                timeout=30, allowed_codes=(0, 1),
            )
            metadata = err.decode(errors='replace')
            match = re.search(r'Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)', metadata)
            if not match:
                raise RuntimeError(f"Invalid media streams or duration: {path.name}")
            h, m, s = map(float, match.groups())
            duration = h * 3600 + m * 60 + s
            if duration <= 0:
                raise RuntimeError(f"Media has no positive duration: {path.name}")
            after = path.stat()
            if (after.st_size, after.st_mtime_ns, after.st_ctime_ns, after.st_ino) != key[1:]:
                raise RuntimeError(f'Media changed during validation: {path.name}')
            cache[key] = (duration, 'Video:' in metadata, 'Audio:' in metadata)
            while len(cache) > _PROBE_CACHE_SIZE:
                cache.popitem(last=False)
        cache.move_to_end(key)
        duration, has_video, has_audio = cache[key]
    if (require_video and not has_video) or (require_audio and not has_audio):
        raise RuntimeError(f"Invalid media streams or duration: {path.name}")
    return duration


async def validate_duration(path: Path, expected: float, *, video: bool = False, audio: bool = False) -> float:
    actual = await probe_media(path, require_video=video, require_audio=audio)
    if abs(actual - expected) > max(0.3, min(1.0, expected * 0.001)):
        raise RuntimeError(f"Media duration mismatch for {path.name}: expected {expected:.3f}s, got {actual:.3f}s")
    return actual
