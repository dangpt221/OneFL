"""Configured narrator defaults without converting explicit saved speaker voices."""
from pathlib import Path
from unittest.mock import AsyncMock

import pytest
from sqlalchemy import select

from app.config import Settings, settings
from app.models.project import Project
from app.models.speaker import SpeakerProfile
from app.models.subtitle import SubtitleCue
from tests.test_reliability import isolated_db

NGOC_HUYEN = 'vieneu-ngoc-huyen'
NAM_MINH = 'vi-VN-NamMinhNeural'
HOAI_MY = 'vi-VN-HoaiMyNeural'


def test_canonical_default_and_example_configuration(monkeypatch):
    monkeypatch.delenv('DEFAULT_TTS_VOICE', raising=False)
    assert Settings(_env_file=None).DEFAULT_TTS_VOICE == NGOC_HUYEN
    example = (Path(__file__).parents[1] / '.env.example').read_text(encoding='utf-8')
    assert f'DEFAULT_TTS_VOICE={NGOC_HUYEN}' in example.splitlines()


@pytest.mark.parametrize('configured', [NGOC_HUYEN, 'nova'])
def test_all_request_and_response_defaults_follow_current_settings(monkeypatch, configured):
    from app.schemas.project import ProjectResponse
    from app.schemas.speaker import SpeakerProfileCreate, SpeakerProfileResponse
    from app.schemas.tts import ProjectDubRequest
    from app.agent.tools import GenerateDubbingAudioInput
    monkeypatch.setattr(settings, 'DEFAULT_TTS_VOICE', configured)
    project_fields = dict(id='p', title='fixture', source_language='zh', target_language='vi',
                          status='CREATED', current_stage='INITIALIZING', progress_percentage=0)
    speaker_fields = dict(id='s', project_id='p', speaker_tag='NARRATOR', gender='female', age_group='adult')
    assert ProjectResponse(**project_fields).default_voice == configured
    assert SpeakerProfileCreate(speaker_tag='NARRATOR').tts_voice == configured
    assert SpeakerProfileResponse(**speaker_fields).tts_voice == configured
    assert ProjectDubRequest().voice == configured
    assert GenerateDubbingAudioInput(text='Nghe thử').voice == configured
    for explicit in (NAM_MINH, HOAI_MY):
        assert ProjectResponse(**project_fields, default_voice=explicit).default_voice == explicit
        assert SpeakerProfileCreate(speaker_tag='NARRATOR', tts_voice=explicit).tts_voice == explicit
        assert SpeakerProfileResponse(**speaker_fields, tts_voice=explicit).tts_voice == explicit
        assert ProjectDubRequest(voice=explicit).voice == explicit
        assert GenerateDubbingAudioInput(text='Nghe thử', voice=explicit).voice == explicit


@pytest.mark.asyncio
async def test_persisted_defaults_resolve_at_insert_and_preserve_explicit_voices(isolated_db, monkeypatch):
    for index, configured in enumerate((NGOC_HUYEN, 'nova')):
        monkeypatch.setattr(settings, 'DEFAULT_TTS_VOICE', configured)
        project = Project(title=f'dynamic narrator {index}')
        saved = Project(title=f'explicit narrator {index}', default_voice=HOAI_MY)
        isolated_db.add_all([project, saved])
        await isolated_db.flush()
        speaker = SpeakerProfile(project_id=project.id, speaker_tag='FEMALE')
        male = SpeakerProfile(project_id=project.id, speaker_tag='MALE', gender='male', tts_voice=NAM_MINH)
        isolated_db.add_all([speaker, male])
        await isolated_db.commit()
        for row in (project, saved, speaker, male):
            await isolated_db.refresh(row)
        assert project.default_voice == speaker.tts_voice == configured
        assert saved.default_voice == HOAI_MY and male.tts_voice == NAM_MINH


@pytest.mark.asyncio
async def test_project_create_api_persists_configured_default(isolated_db, monkeypatch):
    from app.api.v1.projects import create_project
    from app.schemas.project import ProjectCreate
    monkeypatch.setattr(settings, 'DEFAULT_TTS_VOICE', NGOC_HUYEN)
    result = await create_project(ProjectCreate(title='new project narrator'), isolated_db)
    assert result.default_voice == NGOC_HUYEN
    assert (await isolated_db.get(Project, result.id)).default_voice == NGOC_HUYEN


@pytest.mark.asyncio
async def test_speaker_create_fallback_and_upsert_preserve_saved_male_voice(isolated_db, monkeypatch):
    from app.api.v1.speakers import create_speaker_profile
    from app.schemas.speaker import SpeakerProfileCreate
    monkeypatch.setattr(settings, 'DEFAULT_TTS_VOICE', NGOC_HUYEN)
    project = Project(title='speaker narrator defaults')
    isolated_db.add(project)
    await isolated_db.commit()
    female = await create_speaker_profile(project.id, SpeakerProfileCreate(speaker_tag='FEMALE', tts_voice=None), isolated_db)
    assert female.tts_voice == NGOC_HUYEN
    await create_speaker_profile(project.id, SpeakerProfileCreate(speaker_tag='MALE', gender='male', tts_voice=NAM_MINH), isolated_db)
    saved = await create_speaker_profile(project.id, SpeakerProfileCreate(speaker_tag='MALE', display_name='Updated name'), isolated_db)
    assert saved.display_name == 'Updated name' and saved.tts_voice == NAM_MINH
    changed = await create_speaker_profile(project.id, SpeakerProfileCreate(speaker_tag='MALE', tts_voice=HOAI_MY), isolated_db)
    assert changed.tts_voice == HOAI_MY


@pytest.mark.asyncio
@pytest.mark.parametrize('saved_voice', [None, NAM_MINH, HOAI_MY])
async def test_project_dub_shortcut_uses_saved_voice_then_configured_default(isolated_db, monkeypatch, saved_voice):
    from fastapi import BackgroundTasks
    from app.api.v1.projects import trigger_project_dubbing
    import app.api.v1.tts as tts_api
    monkeypatch.setattr(settings, 'DEFAULT_TTS_VOICE', NGOC_HUYEN)
    project = Project(title='dub shortcut default')
    isolated_db.add(project)
    await isolated_db.flush()
    project.default_voice = saved_voice
    await isolated_db.commit()
    start = AsyncMock(return_value={'success': True, 'job_id': 'fixture'})
    monkeypatch.setattr(tts_api, 'start_project_dubbing', start)
    await trigger_project_dubbing(project.id, BackgroundTasks(), isolated_db)
    assert start.await_args.args[2].voice == (saved_voice or NGOC_HUYEN)


@pytest.mark.asyncio
@pytest.mark.parametrize('voice', [None, NAM_MINH])
async def test_agent_preview_uses_configured_default_and_preserves_explicit_choice(monkeypatch, voice):
    from app.agent.tools import agent_toolkit
    from app.services.tts_service import tts_service
    monkeypatch.setattr(settings, 'DEFAULT_TTS_VOICE', NGOC_HUYEN)
    preview = AsyncMock(return_value={'preview_url': '/static/previews/local/fixture.mp3'})
    monkeypatch.setattr(tts_service, 'generate_preview', preview)
    args = {'text': 'Xin chào, đây là giọng đọc thử.'}
    if voice:
        args['voice'] = voice
    result = await agent_toolkit.execute('generate_dubbing_audio', args)
    assert preview.await_args.kwargs['voice'] == (voice or NGOC_HUYEN)
    assert result['voice'] == (voice or NGOC_HUYEN)


@pytest.mark.asyncio
@pytest.mark.parametrize('saved_project_voice', [None, HOAI_MY])
async def test_speaker_profiling_default_keeps_male_explicit_and_existing_voices(isolated_db, monkeypatch, saved_project_voice):
    from app.services.workflow_engine import workflow_engine
    from app.services.speaker_profiler import speaker_profiler
    from app.services.translation_service import translation_service
    monkeypatch.setattr(settings, 'DEFAULT_TTS_VOICE', NGOC_HUYEN)
    monkeypatch.setattr(settings, 'ENABLE_SPEAKER_PROFILER', True)
    project = Project(title='implicit female narrator', video_duration_seconds=1.)
    isolated_db.add(project)
    await isolated_db.flush()
    project.default_voice = saved_project_voice
    isolated_db.add_all([
        SubtitleCue(project_id=project.id, cue_index=1, start_time=0, end_time=1., original_text='Hello', speaker_tag='FEMALE'),
        SpeakerProfile(project_id=project.id, speaker_tag='SAVED', gender='male', tts_voice=NAM_MINH),
    ])
    await isolated_db.commit()
    analysis = {'speakers': {
        'FEMALE': {'gender': 'female'}, 'MALE': {'gender': 'male'},
        'EXPLICIT': {'gender': 'female', 'tts_voice': 'nova'},
        'SAVED': {'gender': 'female', 'tts_voice': 'nova'},
    }, 'relationships': []}
    monkeypatch.setattr(speaker_profiler, 'analyze_speakers_and_matrix', AsyncMock(return_value=analysis))
    monkeypatch.setattr(translation_service, 'translate_project_cues', AsyncMock(return_value=[
        {'cue_index': 1, 'translated_text': 'Xin chào'}]))
    await workflow_engine.run_pipeline(isolated_db, project.id, start_stage='SPEAKER_PROFILING')
    speakers = {speaker.speaker_tag: speaker.tts_voice for speaker in (await isolated_db.execute(
        select(SpeakerProfile).where(SpeakerProfile.project_id == project.id))).scalars()}
    assert project.status == 'WAITING_REVIEW'
    assert speakers == {'FEMALE': saved_project_voice or NGOC_HUYEN, 'MALE': NAM_MINH,
                        'EXPLICIT': 'nova', 'SAVED': NAM_MINH}
