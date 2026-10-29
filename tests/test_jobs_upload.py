import asyncio
import io
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException, UploadFile
from sqlalchemy import select

from app.models.project import Project
from tests.test_reliability import isolated_db


@pytest.mark.asyncio
async def test_job_claim_is_atomic_and_payload_is_persisted(isolated_db):
    from app.services.job_service import job_service
    from app.models.job import Job
    project = Project(title='job audit')
    isolated_db.add(project)
    await isolated_db.commit()
    job = await job_service.enqueue(isolated_db, project.id, 'DUBBING', {'voice': 'nova', 'speed': 1.2})
    job_id = job.id
    with pytest.raises(HTTPException) as error:
        await job_service.enqueue(isolated_db, project.id, 'DUBBING', {'voice': 'onyx'})
    assert error.value.status_code == 409
    stored = (await isolated_db.execute(select(Job).where(Job.id == job_id))).scalar_one()
    assert stored.payload['speed'] == 1.2


@pytest.mark.asyncio
async def test_queued_job_cancel_releases_project(isolated_db):
    from app.services.job_service import job_service
    project = Project(title='cancel audit')
    isolated_db.add(project)
    await isolated_db.commit()
    job = await job_service.enqueue(isolated_db, project.id, 'PIPELINE', {})
    await job_service.cancel(isolated_db, project.id)
    await isolated_db.refresh(job)
    await isolated_db.refresh(project)
    assert job.status == 'CANCELLED'
    assert project.active_job_id is None


@pytest.mark.asyncio
async def test_chunk_upload_requires_complete_manifest_and_retry_is_idempotent(isolated_db):
    from app.services.storage_service import storage_service
    info = await storage_service.begin_upload('audit', 'test.mp4', 8, 2)
    upload_id = info['upload_id']
    await storage_service.receive_chunk('audit', upload_id, 1, 4, UploadFile(file=io.BytesIO(b'tail')))
    with pytest.raises(ValueError, match='incomplete'):
        await storage_service.finalize_upload('audit', upload_id)
    await storage_service.receive_chunk('audit', upload_id, 0, 0, UploadFile(file=io.BytesIO(b'head')))
    await storage_service.receive_chunk('audit', upload_id, 1, 4, UploadFile(file=io.BytesIO(b'tail')))
    path = await storage_service.finalize_upload('audit', upload_id)
    assert path.read_bytes() == b'headtail'
    assert await storage_service.finalize_upload('audit', upload_id) == path


@pytest.mark.asyncio
async def test_upload_rejects_conflicting_chunk_retry(isolated_db):
    from app.services.storage_service import storage_service
    info = await storage_service.begin_upload('audit', 'test.mp4', 4, 1)
    await storage_service.receive_chunk('audit', info['upload_id'], 0, 0, UploadFile(file=io.BytesIO(b'head')))
    with pytest.raises(ValueError, match='conflict'):
        await storage_service.receive_chunk('audit', info['upload_id'], 0, 0, UploadFile(file=io.BytesIO(b'diff')))


@pytest.mark.asyncio
async def test_separate_upload_sessions_never_retain_old_tail(isolated_db):
    from app.services.storage_service import storage_service
    paths = []
    for content in (b'longcontent', b'new'):
        info = await storage_service.begin_upload('audit', 'test.mp4', len(content), 1)
        await storage_service.receive_chunk('audit', info['upload_id'], 0, 0, UploadFile(file=io.BytesIO(content)))
        paths.append(await storage_service.finalize_upload('audit', info['upload_id']))
    assert paths[0] != paths[1]
    assert paths[1].read_bytes() == b'new'


def test_subtitle_schemas_reject_invalid_time_and_required_null():
    from app.schemas.subtitle import SubtitleCueCreate, SubtitleCueUpdate
    from pydantic import ValidationError
    for start, end in ((-1, 2), (3, 2), (0, float('inf'))):
        with pytest.raises(ValidationError):
            SubtitleCueCreate(cue_index=1, start_time=start, end_time=end, original_text='a')
    with pytest.raises(ValidationError):
        SubtitleCueUpdate(original_text=None)
