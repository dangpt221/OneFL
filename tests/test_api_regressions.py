import json
from unittest.mock import AsyncMock
import httpx
import pytest
import pytest_asyncio
from app.database import get_db
from app.models.project import Project
from app.schemas.subtitle import SubtitleCueCreate, SubtitleCueUpdate
from tests.test_reliability import isolated_db


@pytest.mark.asyncio
async def test_subtitle_create_delete_keeps_export_files_in_sync(isolated_db):
    from app.api.v1.subtitles import create_subtitle_cue, delete_subtitle_cue
    from app.services.storage_service import storage_service
    project = Project(title='subtitle CRUD')
    isolated_db.add(project)
    await isolated_db.commit()
    item = await create_subtitle_cue(project.id, SubtitleCueCreate(cue_index=1, start_time=0, end_time=2, original_text='hello', translated_text='Xin chào'), isolated_db)
    srt = storage_service.get_project_dir(project.id) / 'subtitles.srt'
    assert srt.is_file() and 'Xin chào' in srt.read_text(encoding='utf-8')
    await delete_subtitle_cue(project.id, item.id, isolated_db)
    assert not srt.read_text(encoding='utf-8').strip()


@pytest.mark.asyncio
async def test_partial_timing_patch_cannot_reverse_cue(isolated_db):
    from app.api.v1.subtitles import create_subtitle_cue, update_subtitle_cue
    from fastapi import HTTPException
    project = Project(title='timing')
    isolated_db.add(project)
    await isolated_db.commit()
    item = await create_subtitle_cue(project.id, SubtitleCueCreate(cue_index=1, start_time=0, end_time=2, original_text='hello'), isolated_db)
    with pytest.raises(HTTPException) as exc:
        await update_subtitle_cue(project.id, item.id, SubtitleCueUpdate(start_time=5), isolated_db)
    assert exc.value.status_code == 422


@pytest.mark.asyncio
async def test_glossary_auto_extract_reaches_provider_and_surfaces_failure(isolated_db, monkeypatch):
    from app.api.v1.glossary import auto_extract_glossary
    from app.models.subtitle import SubtitleCue
    from app.services.llm_router import llm_router
    project = Project(title='extract')
    isolated_db.add(project)
    await isolated_db.flush()
    isolated_db.add(SubtitleCue(project_id=project.id, cue_index=1, start_time=0, end_time=2, original_text='hello'))
    await isolated_db.commit()
    monkeypatch.setattr(llm_router, 'generate_completion', AsyncMock(return_value='{"terms": []}'))
    assert await auto_extract_glossary(project.id, isolated_db) == []
    monkeypatch.setattr(llm_router, 'generate_completion', AsyncMock(side_effect=RuntimeError('provider offline')))
    with pytest.raises(RuntimeError):
        await auto_extract_glossary(project.id, isolated_db)


@pytest.mark.asyncio
async def test_agent_tts_speaks_requested_text_and_translation_executes(monkeypatch):
    from app.agent.tools import agent_toolkit
    from app.services.tts_service import tts_service
    from app.services.translation_service import translation_service
    preview = AsyncMock(return_value={'preview_url': '/audio.mp3'})
    monkeypatch.setattr(tts_service, 'generate_preview', preview)
    await agent_toolkit.execute('generate_dubbing_audio', {'text': 'Đọc đúng câu này'})
    assert preview.call_args.kwargs['custom_text'] == 'Đọc đúng câu này'
    translate = AsyncMock(return_value=[{'cue_index': 1, 'translated_text': 'Xin chào'}])
    monkeypatch.setattr(translation_service, 'translate_project_cues', translate)
    result = await agent_toolkit.execute('translate_subtitle_chunk', {'cues': [{'id': 1, 'text': 'Hello', 'duration': 3}]})
    assert result['translations'][0]['translated_text'] == 'Xin chào'


@pytest.mark.asyncio
async def test_retranslation_honors_overrides_and_source_path(isolated_db, monkeypatch):
    from app.api.v1.subtitles import _retranslate_cues, create_subtitle_cue
    from app.schemas.translation import RetranslateRequest
    from app.services.translation_service import translation_service
    from pathlib import Path
    project = Project(title='retranslate', local_video_path='source.mp4')
    isolated_db.add(project)
    await isolated_db.commit()
    cue = await create_subtitle_cue(project.id, SubtitleCueCreate(cue_index=1, start_time=0, end_time=3, original_text='hello'), isolated_db)
    translate = AsyncMock(return_value=[{'cue_index': 1, 'translated_text': 'new translation', 'has_guardrail_violation': False}])
    monkeypatch.setattr(translation_service, 'translate_project_cues', translate)
    await _retranslate_cues(project.id, RetranslateRequest(cue_ids=[cue.id], model_override='chosen', temperature=.2), isolated_db)
    args = translate.call_args.kwargs
    assert args['model_override'] == 'chosen' and args['temperature'] == .2
    assert args['video_path'] == Path('source.mp4') and args['preserve_edited'] is False
    assert cue.translated_text == 'new translation'
