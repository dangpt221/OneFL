import os
import shutil
import asyncio
import hashlib
import json
import re
import uuid
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional, Union
from fastapi import UploadFile
import aiofiles
from app.config import settings


class StorageService:
    def __init__(self):
        self.upload_dir = settings.UPLOAD_DIR
        self.output_dir = settings.OUTPUT_DIR
        self.scratch_dir = settings.TEMP_SCRATCH_DIR
        self.ensure_dirs()

    def ensure_dirs(self):
        self.upload_dir.mkdir(parents=True, exist_ok=True)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.scratch_dir.mkdir(parents=True, exist_ok=True)

    def get_project_dir(self, project_id: str) -> Path:
        if not re.fullmatch(r'[A-Za-z0-9_-]{1,128}', project_id):
            raise ValueError('Invalid project identifier')
        p_dir = self.output_dir / project_id
        p_dir.mkdir(parents=True, exist_ok=True)
        return p_dir

    def get_project_scratch_dir(self, project_id: str) -> Path:
        if not re.fullmatch(r'[A-Za-z0-9_-]{1,128}', project_id):
            raise ValueError('Invalid project identifier')
        s_dir = self.scratch_dir / project_id
        s_dir.mkdir(parents=True, exist_ok=True)
        return s_dir

    async def save_upload_file_stream(
        self,
        project_id: str,
        upload_file: UploadFile,
        chunk_size: int = 1024 * 1024 * 8
    ) -> Path:
        """Streams large uploaded video file to disk in chunks to prevent OOM crash on 10h/50GB files."""
        p_dir = self.get_project_dir(project_id)
        filename = upload_file.filename or "video.mp4"
        if Path(filename).suffix.lower() not in {'.mp4', '.mkv', '.mov', '.webm', '.avi', '.m4v'}:
            raise ValueError('Unsupported video extension')
        declared = getattr(upload_file, 'size', None)
        if declared is not None and not 0 < declared <= settings.MAX_UPLOAD_BYTES:
            raise ValueError('Invalid upload size')
        if declared and shutil.disk_usage(p_dir).free < declared * 2 + 64 * 1024**2:
            raise ValueError('Insufficient disk space for upload and processing')
        safe_filename = ''.join(c for c in filename if c.isalnum() or c in '._- ')
        file_path = p_dir / f"original_{uuid.uuid4().hex}_{safe_filename}"
        count = 0
        try:
            async with aiofiles.open(file_path, 'wb') as f:
                while chunk := await upload_file.read(min(chunk_size, 8 * 1024**2)):
                    count += len(chunk)
                    if count > settings.MAX_UPLOAD_BYTES:
                        raise ValueError('Upload size quota exceeded')
                    await f.write(chunk)
            if count == 0 or (declared is not None and count != declared):
                raise ValueError('Upload is empty or incomplete')
        except BaseException:
            file_path.unlink(missing_ok=True)
            raise
        return file_path

    async def write_upload_chunk(
        self,
        project_id: str,
        filename: str,
        chunk_file: UploadFile,
        offset: int
    ) -> Path:
        """Writes a file chunk at a specific offset. Safe for retries and parallel uploads."""
        p_dir = self.get_project_dir(project_id)
        safe_filename = "".join(c for c in filename if c.isalnum() or c in "._- ")
        file_path = p_dir / f"original_{safe_filename}"
        
        if offset < 0 or (offset > 0 and (not file_path.exists() or file_path.stat().st_size != offset)):
            raise ValueError('Chunk offset is not contiguous; use an upload session for retries')
        mode = "r+b" if offset > 0 else "wb"
        async with aiofiles.open(file_path, mode) as f:
            await f.seek(offset)
            while data := await chunk_file.read(1024 * 1024 * 8):
                await f.write(data)
                
        return file_path

    async def save_upload_file(self, project_id: str, filename: str, file_bytes: bytes) -> Path:
        p_dir = self.get_project_dir(project_id)
        # Clean filename
        safe_filename = "".join(c for c in filename if c.isalnum() or c in "._- ")
        file_path = p_dir / f"original_{safe_filename}"
        async with aiofiles.open(file_path, "wb") as f:
            await f.write(file_bytes)
        return file_path

    async def write_text_file(self, file_path: Path, content: str) -> Path:
        file_path.parent.mkdir(parents=True, exist_ok=True)
        temporary = file_path.with_name(f'.{file_path.name}.{uuid.uuid4().hex}.tmp')
        try:
            async with aiofiles.open(temporary, "w", encoding="utf-8") as f:
                await f.write(content)
            temporary.replace(file_path)
        finally:
            temporary.unlink(missing_ok=True)
        return file_path

    async def read_text_file(self, file_path: Path) -> Optional[str]:
        if not file_path.exists():
            return None
        async with aiofiles.open(file_path, "r", encoding="utf-8") as f:
            return await f.read()

    def get_relative_url(self, file_path: Path) -> str:
        """Return URL relative to server static mount."""
        for root, prefix in ((self.output_dir, '/static/data/outputs'), (self.upload_dir, '/static/data/uploads')):
            try:
                rel = file_path.resolve().relative_to(root.resolve())
                return f'{prefix}/{rel.as_posix()}'
            except ValueError:
                continue
        raise ValueError('Artifact is outside configured storage')

    def _upload_dir(self, project_id: str, upload_id: str) -> Path:
        if not re.fullmatch(r'[a-f0-9]{32}', upload_id):
            raise ValueError('Invalid upload ID')
        directory = self.get_project_dir(project_id) / 'uploads' / upload_id
        if not directory.is_dir():
            raise ValueError('Upload session does not exist')
        return directory

    @asynccontextmanager
    async def _upload_lock(self, directory: Path):
        # OS locks serialize API processes and are released automatically if a
        # process dies. No stale lock-file timeout can interrupt an active write.
        with open(directory / '.lock', 'a+b') as lock:
            if lock.tell() == 0:
                lock.write(b'0')
                lock.flush()
            acquired = False
            try:
                for _ in range(600):
                    try:
                        lock.seek(0)
                        if os.name == 'nt':
                            import msvcrt
                            msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
                        else:
                            import fcntl
                            fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                        acquired = True
                        break
                    except OSError:
                        await asyncio.sleep(0.05)
                if not acquired:
                    raise TimeoutError('Upload session is busy')
                yield
            finally:
                if acquired:
                    lock.seek(0)
                    if os.name == 'nt':
                        msvcrt.locking(lock.fileno(), msvcrt.LK_UNLCK, 1)
                    else:
                        fcntl.flock(lock.fileno(), fcntl.LOCK_UN)

    async def begin_upload(self, project_id: str, filename: str, size: int, total_chunks: int) -> dict:
        if not 0 < size <= settings.MAX_UPLOAD_BYTES or not 0 < total_chunks <= 100000:
            raise ValueError('Upload size or chunk count exceeds allowed limits')
        safe = ''.join(c for c in filename if c.isalnum() or c in '._- ')[:200]
        if not safe or Path(safe).suffix.lower() not in {'.mp4', '.mkv', '.mov', '.avi', '.webm', '.m4v'}:
            raise ValueError('Unsupported video filename')
        upload_id = uuid.uuid4().hex
        directory = self.get_project_dir(project_id) / 'uploads' / upload_id
        directory.mkdir(parents=True)
        if shutil.disk_usage(directory).free < size * 2 + 64 * 1024**2:
            raise ValueError('Insufficient storage for upload and finalization')
        manifest = {'upload_id': upload_id, 'filename': safe, 'size': size, 'total_chunks': total_chunks, 'received': {}, 'finalized': False}
        await self.write_text_file(directory / 'manifest.json', json.dumps(manifest))
        return manifest

    async def upload_status(self, project_id: str, upload_id: str) -> dict:
        directory = self._upload_dir(project_id, upload_id)
        return json.loads(await self.read_text_file(directory / 'manifest.json'))

    async def receive_chunk(self, project_id: str, upload_id: str, index: int, offset: int, chunk: UploadFile) -> None:
        directory = self._upload_dir(project_id, upload_id)
        temporary = directory / f'.{uuid.uuid4().hex}.chunk'
        size, checksum = 0, hashlib.sha256()
        try:
            async with aiofiles.open(temporary, 'wb') as stream:
                while data := await chunk.read(1024**2):
                    size += len(data)
                    if size > settings.MAX_UPLOAD_CHUNK_BYTES:
                        raise ValueError('Chunk exceeds maximum size')
                    checksum.update(data)
                    await stream.write(data)
            async with self._upload_lock(directory):
                manifest = await self.upload_status(project_id, upload_id)
                if not 0 <= index < manifest['total_chunks'] or offset < 0 or not size or offset + size > manifest['size']:
                    raise ValueError('Invalid chunk index, offset or size')
                entry = {'offset': offset, 'size': size, 'sha256': checksum.hexdigest()}
                previous = manifest['received'].get(str(index))
                if previous:
                    if previous != entry:
                        raise ValueError('Chunk retry conflict')
                    return
                if manifest['finalized']:
                    raise ValueError('Upload is already finalized')
                for received in manifest['received'].values():
                    if offset < received['offset'] + received['size'] and offset + size > received['offset']:
                        raise ValueError('Chunk offset overlaps received data')
                temporary.replace(directory / f'{index}.part')
                manifest['received'][str(index)] = entry
                await self.write_text_file(directory / 'manifest.json', json.dumps(manifest))
        finally:
            temporary.unlink(missing_ok=True)

    async def finalize_upload(self, project_id: str, upload_id: str) -> Path:
        directory = self._upload_dir(project_id, upload_id)
        async with self._upload_lock(directory):
            manifest = await self.upload_status(project_id, upload_id)
            target = self.get_project_dir(project_id) / f"original_{upload_id}_{manifest['filename']}"
            if manifest['finalized']:
                if not target.exists() or target.stat().st_size != manifest['size']:
                    raise ValueError('Finalized upload artifact is missing')
                return target
            if len(manifest['received']) != manifest['total_chunks']:
                raise ValueError('Upload is incomplete')
            offset = 0
            for index in range(manifest['total_chunks']):
                entry = manifest['received'].get(str(index), {})
                if entry.get('offset') != offset:
                    raise ValueError('Upload is incomplete or non-contiguous')
                offset += entry['size']
            if offset != manifest['size']:
                raise ValueError('Upload is incomplete')
            temporary = target.with_suffix('.assembling')
            def assemble():
                try:
                    with open(temporary, 'wb') as output:
                        for index in range(manifest['total_chunks']):
                            checksum = hashlib.sha256()
                            with open(directory / f'{index}.part', 'rb') as part:
                                while data := part.read(8 * 1024**2):
                                    checksum.update(data)
                                    output.write(data)
                            if checksum.hexdigest() != manifest['received'][str(index)]['sha256']:
                                raise ValueError('Upload checksum mismatch')
                    temporary.replace(target)
                finally:
                    temporary.unlink(missing_ok=True)
            task = asyncio.create_task(asyncio.to_thread(assemble))
            try:
                await asyncio.shield(task)
            except asyncio.CancelledError:
                await task
                raise
            manifest['finalized'] = True
            await self.write_text_file(directory / 'manifest.json', json.dumps(manifest))
            for part in directory.glob('*.part'):
                part.unlink()
            return target

    async def delete_project_files(self, project_id: str) -> None:
        import shutil
        for root in (self.output_dir, self.scratch_dir):
            target = (root / project_id).resolve()
            if target.parent != root.resolve():
                raise ValueError('Project cleanup escaped storage root')
            if target.is_dir():
                await asyncio.to_thread(shutil.rmtree, target)
        # Older versions placed dubbed files directly in the output root.
        for suffix in ('_dubbed.mp3', '_dubbed.mp4'):
            (self.output_dir / f'{project_id}{suffix}').unlink(missing_ok=True)


storage_service = StorageService()
