"""Agent contracts and durable project/media integration regressions."""
import json
from contextlib import asynccontextmanager
from pathlib import Path
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.agent.tools import agent_toolkit
from app.agent.agent_runner import OneFLAgentRunner
from app.models.project import Project
from app.security import current_user
from app.services.llm_router import llm_router
from tests.test_reliability import isolated_db


@pytest.mark.asyncio
async def test_profiler_receives_canonical_asr_text_and_speakers(monkeypatch):
    provider = AsyncMock(return_value=json.dumps({'speakers': {'A': {}, 'B': {}}, 'relationships': []}))
    monkeypatch.setattr(llm_router, 'generate_completion', provider)
    cues = [dict(cue_index=i + 1, start_time=i * 3, end_time=i * 3 + 2,
                 original_text=text, speaker_tag=tag)
            for i, (tag, text) in enumerate([('A', 'Hello'), ('B', 'Goodbye'), ('A', 'Again')])]
    result = await agent_toolkit.execute('analyze_speaker_profiles', {'cues': cues})
    assert set(result['speakers']) == {'A', 'B'}
    assert 'A: Hello' in provider.await_args.args[1] and 'B: Goodbye' in provider.await_args.args[1]


@pytest.mark.asyncio
async def test_relationship_list_flows_into_translation(monkeypatch):
    monkeypatch.setattr(llm_router, 'generate_completion', AsyncMock(return_value='{"translations":[{"id":1,"text":"Hello"}]}'))
    result = await agent_toolkit.execute('translate_subtitle_chunk', {
        'cues': [{'id': 1, 'text': 'Hello', 'duration': 3}], 'relationship_matrix': [],
    })
    assert result['translations'][0]['translated_text'] == 'Hello'


@pytest.mark.asyncio
async def test_qc_reports_only_accepted_translations():
    result = await agent_toolkit.execute('run_subtitle_guardrails', {
        'requested_cues': [{'id': 1, 'text': 'Hello', 'duration': .1}, {'id': 2, 'text': 'Bye', 'duration': 3}],
        'llm_raw_response': '{"translations":[{"id":1,"text":"This is too fast"},{"id":2,"text":"Bye"}]}',
    })
    assert not result['is_valid'] and result['total_passed'] == 1
    assert [x['id'] for x in result['passed_translations']] == [2]


@pytest.mark.asyncio
@pytest.mark.parametrize('bad', ['[]', '{"thought":null,"action":"query_master_glossary","action_input":[]}', 'null'])
async def test_runner_reflects_invalid_decision_shape(bad):
    router = AsyncMock()
    router.generate_completion.side_effect = [bad, '{"thought":"answer","final_answer":"No action required"}']
    result = await OneFLAgentRunner(router).run('A text answer', max_iterations=2)
    assert result.trajectory[0].is_error
    assert result.total_steps == 2


@pytest.mark.asyncio
async def test_runner_does_not_finish_successfully_after_unresolved_tool_error():
    router = AsyncMock()
    router.generate_completion.side_effect = [
        '{"thought":"try","action":"unregistered","action_input":{}}',
        '{"thought":"done","final_answer":"Finished"}',
    ]
    result = await OneFLAgentRunner(router).run('Produce a video', max_iterations=2)
    assert not result.success and result.state == 'FAILED'


@pytest.mark.asyncio
async def test_missing_media_is_not_wrapped_as_success():
    result = await agent_toolkit.execute_tool('inspect_video_media', {'video_path': 'missing-agent-video.mp4'})
    assert not result['success']


@pytest.mark.asyncio
async def test_burn_rejects_style_parameter_that_cannot_affect_existing_ass():
    from pydantic import ValidationError
    with pytest.raises(ValidationError, match='preset'):
        await agent_toolkit.execute('burn_video_subtitles', {
            'video_path': 'a', 'subtitle_path': 'b', 'output_path': 'c', 'preset': 'cinema',
        })


@pytest.mark.asyncio
async def test_preview_forwards_selected_model(monkeypatch):
    from app.services.tts_service import tts_service
    preview = AsyncMock(return_value={'preview_url': '/static/previews/local/test.mp3'})
    monkeypatch.setattr(tts_service, 'generate_preview', preview)
    await agent_toolkit.execute('generate_dubbing_audio', {'text': 'Read this', 'model': 'tts-1-hd'})
    assert preview.await_args.kwargs['model'] == 'tts-1-hd'


def wire_sessions(db, monkeypatch):
    import app.database as database
    import app.services.private_media as private_media
    import importlib
    factory = async_sessionmaker(db.bind, expire_on_commit=False)
    @asynccontextmanager
    async def sessions():
        async with factory() as session:
            yield session
    monkeypatch.setattr(database, 'get_async_session', sessions)
    monkeypatch.setattr(private_media, 'get_async_session', sessions)
    monkeypatch.setattr(importlib.import_module('app.services.agent_project_service'), 'get_async_session', sessions)
    monkeypatch.setattr(importlib.import_module('app.services.job_service'), 'get_async_session', sessions)
    return sessions


@pytest.mark.asyncio
async def test_project_job_tools_enforce_owner_and_admission(isolated_db, monkeypatch):
    wire_sessions(isolated_db, monkeypatch)
    project = Project(title='owned agent project', user_id='alice')
    isolated_db.add(project)
    await isolated_db.commit()
    handle = current_user.set('bob')
    try:
        with pytest.raises(HTTPException) as denied:
            await agent_toolkit.execute('start_project_pipeline', {'project_id': project.id})
        assert denied.value.status_code == 404
    finally:
        current_user.reset(handle)

    handle = current_user.set('alice')
    try:
        queued = await agent_toolkit.execute('start_project_pipeline', {'project_id': project.id})
        assert queued['status'] == 'QUEUED' and queued['job_id']
        with pytest.raises(HTTPException) as duplicate:
            await agent_toolkit.execute('start_project_pipeline', {'project_id': project.id})
        assert duplicate.value.status_code == 409
        pending = await agent_toolkit.execute('wait_for_job', {'project_id': project.id, 'job_id': queued['job_id'], 'timeout_seconds': .01})
        assert pending['status'] == 'QUEUED'
        await agent_toolkit.execute('cancel_project_job', {'project_id': project.id})
        stopped = await agent_toolkit.execute('get_job_status', {'project_id': project.id, 'job_id': queued['job_id']})
        assert stopped['status'] == 'CANCELLED'
    finally:
        current_user.reset(handle)


@pytest.mark.asyncio
async def test_runner_reports_queued_project_as_pending(isolated_db, monkeypatch):
    wire_sessions(isolated_db, monkeypatch)
    project = Project(title='Runner queue evidence')
    isolated_db.add(project)
    await isolated_db.commit()
    router = AsyncMock()
    router.generate_completion.side_effect = [
        '{"thought":"queue","action":"start_project_pipeline","action_input":{}}',
        '{"thought":"done","final_answer":"Video complete"}',
    ]
    result = await OneFLAgentRunner(router).run('Process project', context={'project_id': project.id}, max_iterations=2)
    assert not result.success and result.state == 'PENDING'
    assert result.jobs[0]['status'] == 'QUEUED'
    assert 'Video complete' not in result.final_answer


@pytest.mark.asyncio
async def test_agent_project_media_chain_uses_real_extraction_export_and_burn(isolated_db, monkeypatch):
    from app.config import settings
    from app.models.job import Job
    from app.services.asr_service import asr_service
    from app.services.job_service import JobService
    from app.services.media_process import run_media, probe_media
    from app.services.storage_service import storage_service
    from app.services.video_burner import video_burner
    wire_sessions(isolated_db, monkeypatch)
    project = Project(title='Real media Agent chain', user_id='alice', source_language='en')
    isolated_db.add(project)
    await isolated_db.commit()
    pid = project.id
    source = storage_service.get_project_dir(pid) / 'source.mp4'
    await run_media([settings.get_ffmpeg_bin(), '-y', '-f', 'lavfi', '-i', 'testsrc=size=320x240:rate=15',
                     '-f', 'lavfi', '-i', 'sine=frequency=440:sample_rate=24000', '-t', '3',
                     '-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-c:a', 'aac', str(source)])
    project.local_video_path = str(source)
    project.original_video_url = storage_service.get_relative_url(source)
    await isolated_db.commit()
    monkeypatch.setattr(settings, 'ENABLE_VISUAL_CONTEXT', False)
    monkeypatch.setattr(video_burner, '_cached_encoder', 'libx264')
    transcribed = [dict(cue_index=i + 1, original_text=text, speaker_tag=tag, start_time=start, end_time=end)
                   for i, (text, tag, start, end) in enumerate([('Hello', 'A', .1, 1.2), ('Goodbye', 'B', 1.5, 2.8)])]
    async def recognition(**kwargs):
        assert current_user.get() == 'alice'
        assert Path(kwargs['audio_path']).is_file()
        assert kwargs['source_language'] == 'en'
        return transcribed
    asr = AsyncMock(side_effect=recognition)
    monkeypatch.setattr(asr_service, 'transcribe_audio', asr)
    monkeypatch.setattr(llm_router, 'generate_completion', AsyncMock(return_value='{"translations":[{"id":1,"text":"Hello"},{"id":2,"text":"Bye"}]}'))
    worker = JobService()

    async def execute(job_id):
        from app.services.agent_project_service import get_async_session
        async with get_async_session() as db:
            job = await db.get(Job, job_id)
            job.status = 'RUNNING'
            await db.commit()
        previous_actor = current_user.get()
        await worker._execute(job_id)
        assert current_user.get() == previous_actor

    handle = current_user.set('alice')
    try:
        queued = await agent_toolkit.execute('extract_and_transcribe_audio', {'project_id': pid})
        assert asr.await_count == 0
    finally:
        current_user.reset(handle)
    await execute(queued['job_id'])  # worker starts outside the request's Alice context
    handle = current_user.set('alice')
    try:
        state = await agent_toolkit.execute('get_job_status', {'project_id': pid, 'job_id': queued['job_id']})
        assert state['status'] == 'SUCCEEDED', state['error']
        assert state['result']['total_cues'] == 2
        page = await agent_toolkit.execute('get_project_context', {'project_id': pid, 'offset': 1, 'limit': 1})
        assert page['total_cues'] == 2 and len(page['cues']) == 1 and page['cues'][0]['speaker_tag'] == 'B'
        with pytest.raises(HTTPException, match='409'):
            await agent_toolkit.execute('extract_and_transcribe_audio', {'project_id': pid})
        translation = await agent_toolkit.execute('start_project_pipeline', {'project_id': pid, 'stage': 'TRANSLATING'})
        await execute(translation['job_id'])
        status = await agent_toolkit.execute('get_job_status', {'project_id': pid, 'job_id': translation['job_id']})
        assert status['status'] == 'SUCCEEDED', status['error']
        exported = await agent_toolkit.execute('export_subtitles', {'project_id': pid, 'preset': 'cinema', 'bilingual': True})
        assert Path(exported['subtitle_path']).is_file()
        assert 'Hello' in Path(exported['subtitle_path']).read_text(encoding='utf-8')
        burn = await agent_toolkit.execute('burn_video_subtitles', {'project_id': pid, 'clean_chinese_mode': 'none'})
        with pytest.raises(HTTPException) as conflict:
            await agent_toolkit.execute('burn_video_subtitles', {'project_id': pid})
        assert conflict.value.status_code == 409
        await execute(burn['job_id'])
        finished = await agent_toolkit.execute('get_job_status', {'project_id': pid, 'job_id': burn['job_id']})
        assert finished['status'] == 'SUCCEEDED', finished['error']
        assert finished['artifact_current'] and Path(finished['result']['output_path']).is_file()
        assert await probe_media(Path(finished['result']['output_path']), require_video=True) == pytest.approx(3, abs=.15)
        page = await agent_toolkit.execute('get_project_context', {'project_id': pid})
        assert not page['active_job_id'] and page['burned_video_url'] == finished['result']['output_url']
        inspected = await agent_toolkit.execute('inspect_video_media', {'video_path': finished['result']['output_path']})
        assert inspected['duration_seconds'] == pytest.approx(3, abs=.15)
        router = AsyncMock()
        router.generate_completion.return_value = '{"thought":"verified","final_answer":"Ready"}'
        result = await OneFLAgentRunner(router).run('Verify output', {'project_id': pid, 'expected_artifact': 'burned_video'}, 1)
        assert result.success and result.state == 'COMPLETED'
        from app.services.agent_project_service import get_async_session
        from app.services.project_changes import commit_project_changes
        async with get_async_session() as db:
            await commit_project_changes(db, pid, invalidate_audio=True)
        stale = await agent_toolkit.execute('get_job_status', {'project_id': pid, 'job_id': burn['job_id']})
        assert stale['status'] == 'SUCCEEDED' and not stale['artifact_current']
        result = await OneFLAgentRunner(router).run('Verify current output', {'project_id': pid, 'expected_artifact': 'burned_video'}, 1)
        assert not result.success and result.state == 'FAILED'
        step = 0
        async def choose(**kwargs):
            nonlocal step
            step += 1
            if step == 1:
                return '{"thought":"render","action":"burn_video_subtitles","action_input":{"clean_chinese_mode":"none"}}'
            if step == 2:
                from sqlalchemy import select
                async with get_async_session() as db:
                    job = await db.scalar(select(Job).where(Job.project_id == pid, Job.status == 'QUEUED'))
                    jid = job.id
                await execute(jid)
                return json.dumps({'thought': 'check', 'action': 'wait_for_job', 'action_input': {'job_id': jid, 'timeout_seconds': 0}})
            return '{"thought":"verified","final_answer":"Rendered output is ready"}'
        router.generate_completion.side_effect = choose
        result = await OneFLAgentRunner(router).run('Render and verify', {'project_id': pid, 'expected_artifact': 'burned_video'}, 3)
        assert result.success and result.jobs[0]['status'] == 'SUCCEEDED'
    finally:
        current_user.reset(handle)


@pytest.mark.asyncio
async def test_bilingual_srt_and_vtt_keep_both_languages():
    for fmt in ('srt', 'vtt'):
        result = await agent_toolkit.execute('export_subtitles', {'format': fmt, 'bilingual': True,
            'cues': [{'id': 1, 'text': 'Source line', 'translated_text': 'Target line', 'duration': 3}]})
        assert 'Source line\nTarget line' in result['content']


def test_http_agent_handles_bad_shapes_and_preserves_access_errors(monkeypatch):
    from fastapi.testclient import TestClient
    from app.main import app
    from app.agent.agent_runner import agent_runner
    from app.config import settings
    monkeypatch.setattr(settings, 'API_ACCESS_TOKEN', None)
    monkeypatch.setattr(settings, 'AUTH_USERS', {})
    monkeypatch.setattr(agent_runner.llm_router, 'generate_completion', AsyncMock(return_value='[]'))
    with_test = TestClient(app)
    response = with_test.post('/api/v1/agent/chat', json={'goal': 'Bad shape', 'max_iterations': 1})
    assert response.status_code == 200 and response.json()['state'] == 'FAILED'
    async def denied(*args, **kwargs):
        raise HTTPException(404, 'Project not found')
    monkeypatch.setattr(agent_toolkit, 'execute', denied)
    response = with_test.post('/api/v1/agent/execute-tool', json={'tool_name': 'get_project_context', 'arguments': {'project_id': 'other'}})
    assert response.status_code == 404
    with_test.close()


@pytest.mark.asyncio
async def test_job_result_migrates_on_legacy_jobs_table(tmp_path):
    from sqlalchemy import text, inspect
    from sqlalchemy.ext.asyncio import create_async_engine
    from app.services.db_migrator import run_migrations
    engine = create_async_engine(f'sqlite+aiosqlite:///{tmp_path / "legacy-agent.db"}')
    async with engine.begin() as connection:
        await connection.execute(text('CREATE TABLE jobs (id VARCHAR(36) PRIMARY KEY, project_id VARCHAR(36), kind VARCHAR(20))'))
    await run_migrations(engine)
    await run_migrations(engine)
    async with engine.connect() as connection:
        names = await connection.run_sync(lambda c: {x['name'] for x in inspect(c).get_columns('jobs')})
        assert 'result' in names
        assert await connection.scalar(text('SELECT version FROM schema_migrations WHERE version=3')) == 3
    await engine.dispose()


@pytest.mark.asyncio
async def test_agent_media_cancellation_waits_for_asr_exit(isolated_db, monkeypatch):
    import asyncio
    import importlib
    from app.models.job import Job
    from app.services.asr_service import asr_service
    from app.services.job_service import JobService
    from app.services.storage_service import storage_service
    wire_sessions(isolated_db, monkeypatch)
    worker = JobService()
    monkeypatch.setattr(importlib.import_module('app.services.job_service'), 'job_service', worker)
    project = Project(title='Agent cancel')
    isolated_db.add(project)
    await isolated_db.commit()
    audio = storage_service.get_project_dir(project.id) / 'boundary.wav'
    audio.write_bytes(b'provider is mocked')
    started, exited = asyncio.Event(), asyncio.Event()
    async def blocked(**kwargs):
        started.set()
        try:
            await asyncio.sleep(60)
        finally:
            exited.set()
    monkeypatch.setattr(asr_service, 'transcribe_audio', blocked)
    queued = await agent_toolkit.execute('extract_and_transcribe_audio', {'audio_path': str(audio)})
    job = await isolated_db.get(Job, queued['job_id'])
    job.status = 'RUNNING'
    await isolated_db.commit()
    task = asyncio.create_task(worker._execute(job.id))
    worker.active[job.id] = task
    try:
        await asyncio.wait_for(started.wait(), 2)
        cancelled = await agent_toolkit.execute('cancel_project_job', {'project_id': project.id})
        assert exited.is_set() and task.done()
        assert cancelled['status'] == 'CANCELLED' and cancelled['active_job_id'] is None
        state = await agent_toolkit.execute('get_job_status', {'project_id': project.id, 'job_id': job.id})
        assert state['status'] == 'CANCELLED' and not state['success'] and state['result'] is None
    finally:
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)
        worker.active.clear()


@pytest.mark.asyncio
async def test_agent_media_payload_survives_recovery(isolated_db, monkeypatch):
    from app.models.job import Job
    from app.services.job_service import JobService
    from app.services.storage_service import storage_service
    wire_sessions(isolated_db, monkeypatch)
    project = Project(title='Agent recovery')
    isolated_db.add(project)
    await isolated_db.commit()
    audio = storage_service.get_project_dir(project.id) / 'boundary.wav'
    audio.write_bytes(b'provider boundary')
    queued = await agent_toolkit.execute('extract_and_transcribe_audio', {'audio_path': str(audio), 'source_language': 'ja'})
    job = await isolated_db.get(Job, queued['job_id'])
    payload = dict(job.payload)
    job.status, job.owner = 'RUNNING', 'previous-process'
    await isolated_db.commit()
    await JobService()._recover()
    await isolated_db.refresh(job)
    assert job.status == 'QUEUED' and job.owner is None
    assert job.payload == payload and job.payload['arguments']['source_language'] == 'ja'


@pytest.mark.asyncio
async def test_project_dubbing_tool_saves_the_same_config_as_http(isolated_db, monkeypatch):
    wire_sessions(isolated_db, monkeypatch)
    project = Project(title='Agent timed dubbing')
    isolated_db.add(project)
    await isolated_db.commit()
    queued = await agent_toolkit.execute('dub_project_video', {'project_id': project.id,
        'voice': 'nova', 'model': 'tts-1-hd', 'speed': 1.3, 'ducking_volume': .2, 'mix_original': False})
    await isolated_db.refresh(project)
    assert queued['status'] == 'QUEUED' and project.active_job_id == queued['job_id']
    assert project.last_dub_config['model'] == 'tts-1-hd' and project.last_dub_config['speed'] == 1.3
    with pytest.raises(HTTPException) as error:
        await agent_toolkit.execute('dub_project_video', {'project_id': project.id, 'voice': 'nova', 'speed': .8})
    assert error.value.status_code == 409
    await isolated_db.refresh(project)
    assert project.last_dub_config['speed'] == 1.3


@pytest.mark.asyncio
async def test_session_cleanup_finishes_before_propagating_socket_cancellation(monkeypatch):
    import asyncio
    import app.database as database
    entered, release, closed = asyncio.Event(), asyncio.Event(), asyncio.Event()
    class Session:
        async def __aenter__(self):
            return self
        async def __aexit__(self, *args):
            return False
        async def rollback(self):
            return None
        async def close(self):
            entered.set()
            await release.wait()
            closed.set()
    monkeypatch.setattr(database, 'AsyncSessionLocal', Session)
    async def socket_snapshot():
        async with database.get_async_session():
            pass
    snapshot = asyncio.create_task(socket_snapshot())
    await entered.wait()
    snapshot.cancel()
    await asyncio.sleep(0)
    release.set()
    with pytest.raises(asyncio.CancelledError):
        await snapshot
    assert closed.is_set(), 'Connection rollback/close was interrupted by socket cancellation'
