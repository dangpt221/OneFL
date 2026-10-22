import pytest
from app.models.project import Project
from tests.test_reliability import isolated_db


@pytest.mark.asyncio
async def test_speaker_and_glossary_mutations_advance_project_content_version(isolated_db):
    from app.api.v1.speakers import create_speaker_profile, update_speaker_profile
    from app.api.v1.glossary import add_glossary_term
    from app.schemas.speaker import SpeakerProfileCreate, SpeakerProfileUpdate
    from app.schemas.glossary import GlossaryTermCreate
    project = Project(title='cross-session synchronization')
    isolated_db.add(project)
    await isolated_db.commit()
    before = getattr(project, 'content_revision', 0)
    await create_speaker_profile(project.id, SpeakerProfileCreate(speaker_tag='A'), isolated_db)
    await isolated_db.refresh(project)
    assert getattr(project, 'content_revision', 0) > before
    before = project.content_revision
    await update_speaker_profile(project.id, 'A', SpeakerProfileUpdate(display_name='Changed remotely'), isolated_db)
    await isolated_db.refresh(project)
    assert project.content_revision > before
    before = project.content_revision
    await add_glossary_term(project.id, GlossaryTermCreate(source_term='test', target_term='thu'), isolated_db)
    await isolated_db.refresh(project)
    assert project.content_revision > before


@pytest.mark.asyncio
async def test_preview_model_is_forwarded_and_has_separate_cache(isolated_db, monkeypatch):
    from app.services.tts_service import tts_service
    from app.services import media_process
    from unittest.mock import AsyncMock
    calls = []
    async def speech(text, **kwargs):
        calls.append(kwargs['model'])
        kwargs['output_path'].write_bytes(b'fixture-audio')
    monkeypatch.setattr(tts_service, 'synthesize_speech', speech)
    monkeypatch.setattr(media_process, 'probe_media', AsyncMock(return_value=1.))
    first = await tts_service.generate_preview('nova', custom_text='Hello', model='tts-1')
    second = await tts_service.generate_preview('nova', custom_text='Hello', model='tts-1-hd')
    await tts_service.generate_preview('nova', custom_text='Hello', model='tts-1-hd')
    assert first['preview_url'] != second['preview_url']
    assert calls == ['tts-1', 'tts-1-hd']


@pytest.mark.asyncio
async def test_content_write_cannot_commit_after_job_claim(isolated_db):
    from app.api.v1.speakers import create_speaker_profile
    from app.schemas.speaker import SpeakerProfileCreate
    from app.models.speaker import SpeakerProfile
    from sqlalchemy import select, func
    from fastapi import HTTPException
    project = Project(title='claimed before edit commit', active_job_id='claimed-job')
    isolated_db.add(project)
    await isolated_db.commit()
    pid = project.id
    with pytest.raises(HTTPException) as error:
        await create_speaker_profile(pid, SpeakerProfileCreate(speaker_tag='RACING_EDIT'), isolated_db)
    assert error.value.status_code == 409
    assert await isolated_db.scalar(select(func.count(SpeakerProfile.id)).where(SpeakerProfile.project_id == pid)) == 0


@pytest.mark.asyncio
async def test_queue_resets_progress_and_preserves_operation_kind(isolated_db):
    from app.services.job_service import JobService
    project = Project(title='render queued after completed translation', progress_percentage=100, burned_video_url='/old.mp4')
    isolated_db.add(project)
    await isolated_db.commit()
    await JobService().enqueue(isolated_db, project.id, 'BURN', {})
    await isolated_db.refresh(project)
    assert project.progress_percentage == 0
    assert getattr(project, 'last_job_kind', None) == 'BURN'
    assert project.burned_video_url is None
