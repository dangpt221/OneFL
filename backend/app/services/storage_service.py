import os
import shutil
from pathlib import Path
from typing import Optional
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
        p_dir = self.output_dir / project_id
        p_dir.mkdir(parents=True, exist_ok=True)
        return p_dir

    def get_project_scratch_dir(self, project_id: str) -> Path:
        s_dir = self.scratch_dir / project_id
        s_dir.mkdir(parents=True, exist_ok=True)
        return s_dir

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
        async with aiofiles.open(file_path, "w", encoding="utf-8") as f:
            await f.write(content)
        return file_path

    async def read_text_file(self, file_path: Path) -> Optional[str]:
        if not file_path.exists():
            return None
        async with aiofiles.open(file_path, "r", encoding="utf-8") as f:
            return await f.read()

    def get_relative_url(self, file_path: Path) -> str:
        """Return URL relative to server static mount."""
        try:
            rel = file_path.relative_to(settings.ROOT_DIR)
            return f"/static/{rel.as_posix()}"
        except Exception:
            return str(file_path)


storage_service = StorageService()
