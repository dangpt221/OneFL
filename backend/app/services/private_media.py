"""Serve artifacts only to the owning project user."""
from pathlib import Path
from fastapi import HTTPException
from fastapi.staticfiles import StaticFiles
from app.database import get_async_session
from app.models.project import Project
from app.security import current_user


class PrivateMediaFiles(StaticFiles):
    async def get_response(self, path: str, scope):
        if path.startswith(('/', '\\')) or '..' in path.replace('\\', '/').split('/'):
            raise HTTPException(404)
        parts = Path(path).parts
        if not parts:
            raise HTTPException(404)
        if parts[0] == 'previews':
            if len(parts) < 3 or parts[1] != current_user.get():
                raise HTTPException(404)
        else:
            async with get_async_session() as db:
                project = await db.get(Project, parts[0])
                if not project or project.user_id != current_user.get():
                    raise HTTPException(404)
        return await super().get_response(path, scope)


async def authorize_media_path(path: Path):
    resolved = path.resolve()
    from app.config import settings
    for root in (settings.OUTPUT_DIR, settings.UPLOAD_DIR):
        try:
            relative = resolved.relative_to(root.resolve())
        except ValueError:
            continue
        if not relative.parts:
            break
        async with get_async_session() as db:
            project = await db.get(Project, relative.parts[0])
            if project and project.user_id == current_user.get():
                return resolved
        break
    raise ValueError('Media path must belong to an accessible project')
