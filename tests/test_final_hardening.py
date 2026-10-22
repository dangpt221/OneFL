import asyncio
import json
import importlib
from unittest.mock import AsyncMock

import pytest
from pydantic import ValidationError
from sqlalchemy.exc import IntegrityError

from app.models.project import Project
from app.models.subtitle import SubtitleCue
from app.schemas.project import ProjectUpdate
from app.services.subtitle_generator import format_timestamp_ass, format_timestamp_srt
from app.services.video_burner import VideoBurner
from tests.test_reliability import isolated_db
from tests.test_job_worker import worker_for


def test_metadata_cannot_forge_job_status_or_clear_required_fields():
    for payload in ({'status': 'COMPLETED'}, {'progress_percentage': 100}, {'title': None}, {'title': ''}):
        with pytest.raises(ValidationError):
            ProjectUpdate(**payload)


def test_zero_masks_do_not_create_full_frame_box_or_empty_crop():
    burner = VideoBurner()
    for mode in ('cinema_bars', 'bottom_bar', 'smart_blur', 'cinema_zoom'):
        assert burner.build_video_filter('a.ass', mode, True, 0, 0) == 'ass=a.ass'


def test_timestamp_rounding_carries_into_next_second():
    assert format_timestamp_ass(59.999) == '0:01:00.00'
    assert format_timestamp_srt(59.9999) == '00:01:00,000'


@pytest.mark.asyncio
async def test_database_prevents_duplicate_cue_index(isolated_db):
    project = Project(title='unique cues')
    isolated_db.add(project)
    await isolated_db.commit()
    isolated_db.add_all([SubtitleCue(project_id=project.id, cue_index=1, start_time=0, end_time=1, original_text='a') for _ in range(2)])
    with pytest.raises(IntegrityError):
        await isolated_db.commit()
    await isolated_db.rollback()


@pytest.mark.asyncio
async def test_force_pipeline_invalidates_previous_artifacts_before_failure(isolated_db):
    from app.services.workflow_engine import workflow_engine
    project = Project(title='old output', burned_video_url='/old.mp4', dubbed_audio_url='/old.wav')
    isolated_db.add(project)
    await isolated_db.commit()
    with pytest.raises(ValueError):
        await workflow_engine.run_pipeline(isolated_db, project.id, force_reprocess=True)
    await isolated_db.refresh(project)
    assert project.burned_video_url is None and project.dubbed_audio_url is None


@pytest.mark.asyncio
async def test_shutdown_renews_lease_until_media_has_stopped(isolated_db, monkeypatch):
    module = importlib.import_module('app.services.job_service')
    worker = worker_for(isolated_db, monkeypatch)
    monkeypatch.setattr(module.settings, 'JOB_LEASE_SECONDS', 0.12)
    worker._lease = AsyncMock(return_value=True)
    entered = asyncio.Event()

    async def inference():
        entered.set()
        try:
            await asyncio.sleep(10)
        except asyncio.CancelledError:
            # Native inference cannot be killed immediately; ownership must stay
            # exclusive while it releases its GPU/process resources.
            await asyncio.sleep(0.2)

    task = asyncio.create_task(inference())
    worker.active['test'] = task
    await entered.wait()
    await worker.stop()
    assert task.done() and worker._lease.await_count >= 2


@pytest.mark.asyncio
async def test_input_replacement_clears_stale_content_and_is_idempotent(isolated_db, tmp_path, monkeypatch):
    routes = importlib.import_module('app.api.v1.projects')
    from sqlalchemy import select
    project = Project(title='replace', burned_video_url='/stale.mp4', extracted_audio_path='/old.wav')
    isolated_db.add(project)
    await isolated_db.flush()
    isolated_db.add(SubtitleCue(project_id=project.id, cue_index=1, start_time=0, end_time=2, original_text='old'))
    await isolated_db.commit()
    source = tmp_path / 'outputs' / project.id / 'new.mp4'
    source.parent.mkdir()
    source.write_bytes(b'input')
    monkeypatch.setattr(routes, 'probe_media', AsyncMock(return_value=3.))
    enqueue = AsyncMock()
    monkeypatch.setattr(routes.job_service, 'enqueue', enqueue)
    await routes.replace_project_source(isolated_db, project.id, source, True)
    assert project.burned_video_url is None and project.extracted_audio_path is None
    assert not (await isolated_db.execute(select(SubtitleCue))).scalars().all()
    await routes.replace_project_source(isolated_db, project.id, source, True)
    enqueue.assert_awaited_once()


def test_glossary_case_and_word_boundaries():
    from app.services.guardrails import SubtitleGuardrails
    raw = json.dumps({'translations': [{'id': 1, 'text': 'Hello'}]})
    valid, _, _ = SubtitleGuardrails.validate_batch([{'id': 1, 'text': 'chair', 'duration': 4}], raw, glossary={'AI': 'artificial intelligence'})
    assert valid
    valid, _, violations = SubtitleGuardrails.validate_batch([{'id': 1, 'text': 'AI', 'duration': 4}], raw,
        glossary=[{'source_term': 'AI', 'target_term': 'HELLO', 'case_sensitive': 'true'}])
    assert not valid and any(item['type'] == 'GLOSSARY_MISMATCH' for item in violations)


@pytest.mark.asyncio
async def test_cleanup_retains_current_artifacts_and_os_lock(isolated_db, tmp_path):
    import os
    import time
    from app.services.artifact_service import cleanup_expired_scratch
    current, obsolete = tmp_path / 'outputs' / 'current.mp4', tmp_path / 'outputs' / 'obsolete.mp4'
    lock = tmp_path / 'scratch' / '.worker.lock'
    for path in (current, obsolete, lock):
        path.write_bytes(b'old')
        os.utime(path, (time.time() - 30 * 86400,) * 2)
    isolated_db.add(Project(title='retention', local_video_path=str(current)))
    await isolated_db.commit()
    assert await cleanup_expired_scratch(isolated_db) == 1
    assert current.exists() and lock.exists() and not obsolete.exists()


@pytest.mark.asyncio
async def test_rejected_burn_does_not_change_running_job_settings(isolated_db, monkeypatch):
    from app.api.v1.pipeline import start_burning
    from app.schemas.translation import BurnOptionsRequest
    from fastapi import BackgroundTasks, HTTPException
    worker = worker_for(isolated_db, monkeypatch)
    project = Project(title='busy', settings_override={'bilingual': False})
    isolated_db.add(project)
    await isolated_db.commit()
    await worker.enqueue(isolated_db, project.id, 'BURN', {})
    with pytest.raises(HTTPException) as error:
        await start_burning(project.id, BackgroundTasks(), BurnOptionsRequest(bilingual=True), isolated_db)
    assert error.value.status_code == 409
    await isolated_db.refresh(project)
    assert project.settings_override['bilingual'] is False


@pytest.mark.asyncio
async def test_gemini_uses_requested_model_and_ignores_thought_parts(monkeypatch):
    import httpx
    from app.services.llm_router import LLMRouter
    module = importlib.import_module('app.services.llm_router')
    client_class = httpx.AsyncClient
    seen = []
    def handle(request):
        seen.append(request)
        return httpx.Response(200, json={'candidates': [{'content': {'parts': [
            {'thought': True, 'text': 'private analysis'}, {'text': '{"translations": []}'},
        ]}}]})
    monkeypatch.setattr(module.httpx, 'AsyncClient', lambda **kwargs: client_class(transport=httpx.MockTransport(handle), **kwargs))
    router = LLMRouter()
    router.gemini_key = 'test-only-credential'
    output = await router._call_gemini('system', 'user', model='requested-model')
    assert output == '{"translations": []}'
    assert '/requested-model:' in str(seen[0].url) and not seen[0].url.query
    assert seen[0].headers['x-goog-api-key'] == 'test-only-credential'
    assert 'thinkingBudget' not in seen[0].content.decode()


@pytest.mark.asyncio
async def test_preserved_manual_translation_keeps_qc_warning(monkeypatch):
    from app.services.translation_service import translation_service
    from app.services.llm_router import llm_router
    completion = AsyncMock(side_effect=AssertionError('Edited cue must stay intact'))
    monkeypatch.setattr(llm_router, 'generate_completion', completion)
    text = ' '.join(['word'] * 40)
    result = await translation_service.translate_project_cues('test', [{
        'cue_index': 1, 'start_time': 0, 'end_time': 1,
        'original_text': 'source', 'translated_text': text, 'is_edited': True,
    }], force_reprocess=True)
    assert result[0]['translated_text'] == text and result[0]['has_guardrail_violation']
    completion.assert_not_awaited()
