"""Audit observations, NOT acceptance tests. Uses isolated DB/storage and mocked providers.

Run from repository root using backend/.venv/Scripts/python.exe.
Assertions document current defects; remove/update them when fixing those defects.
"""
import asyncio
from contextlib import asynccontextmanager
import json
import os
from pathlib import Path
import sys
from unittest.mock import AsyncMock, patch

ROOT = Path(__file__).resolve().parents[2]
WORK = ROOT / 'tmp' / 'agent-review'
WORK.mkdir(parents=True, exist_ok=True)
os.environ.update({
    'DATABASE_URL': 'sqlite+aiosqlite:///:memory:', 'STORAGE_DRIVER': 'local',
    'OUTPUT_DIR': str(WORK / 'outputs'), 'UPLOAD_DIR': str(WORK / 'uploads'),
    'TEMP_SCRATCH_DIR': str(WORK / 'scratch'), 'ENV': 'development',
    'API_ACCESS_TOKEN': '', 'AUTH_USERS': '{}', 'GEMINI_API_KEY': '',
    'OPENAI_API_KEY': '', 'HF_TOKEN': '', 'ENABLE_VISUAL_CONTEXT': 'false',
    'ENABLE_SPEAKER_DIARIZATION': 'false', 'ENABLE_SPEAKER_PROFILER': 'false',
})
sys.path.insert(0, str(ROOT / 'backend'))

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from app.config import settings
from app.database import Base
from app.models.project import Project
from app.agent.tools import agent_toolkit
from app.agent.agent_runner import OneFLAgentRunner
from app.security import current_user
from app.services.llm_router import llm_router
from app.services.asr_service import asr_service
from app.services.audio_service import audio_service
from app.services.video_burner import video_burner
from app.services.storage_service import storage_service
from app.services.tts_service import tts_service

observations = []


def record(name, **data):
    observations.append({'name': name, **data})
    print(name, json.dumps(data, ensure_ascii=True))


async def main():
    engine = create_async_engine('sqlite+aiosqlite:///:memory:')
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)

    @asynccontextmanager
    async def sessions():
        async with factory() as db:
            yield db

    async with factory() as db:
        project = Project(title='isolated Agent review', user_id='alice', active_job_id='existing-job')
        db.add(project)
        await db.commit()
        pid = project.id
    directory = settings.OUTPUT_DIR / pid
    directory.mkdir(parents=True, exist_ok=True)
    video, audio, subtitle, output = [directory / name for name in ('source.mp4', 'audio.wav', 'sub.ass', 'burn.mp4')]
    video.write_bytes(b'This is not a valid video')
    audio.write_bytes(b'fixture boundary only')
    subtitle.write_text('[Script Info]\n', encoding='utf-8')
    storage_service.output_dir = settings.OUTPUT_DIR
    storage_service.scratch_dir = settings.TEMP_SCRATCH_DIR
    handle = current_user.set('alice')
    try:
        with patch('app.services.private_media.get_async_session', sessions):
            # Metadata inspection currently only stats the file.
            inspection = await agent_toolkit.execute('inspect_video_media', {'video_path': str(video)})
            assert inspection['status'] == 'OK' and 'duration' not in inspection
            record('inspect_only_checks_file', result=inspection)

            # ASR output cannot be fed to the profiler without key adaptation.
            transcript = [dict(cue_index=i + 1, original_text=text, speaker_tag=tag,
                               start_time=i * 3., end_time=(i + 1) * 3.)
                          for i, (tag, text) in enumerate([('A', 'Hello'), ('B', 'Goodbye'), ('A', 'Again')])]
            with patch.object(asr_service, 'transcribe_audio', AsyncMock(return_value=transcript)), \
                 patch.object(audio_service, 'extract_audio_16k_mono', AsyncMock()) as extraction:
                transcribed = await agent_toolkit.execute('extract_and_transcribe_audio', {'audio_path': str(audio)})
                assert len(transcribed['cues']) == 3 and extraction.await_count == 0
                record('transcribe_requires_existing_audio', returned_cues=len(transcribed['cues']), audio_extraction_calls=extraction.await_count)

            profile = {'speakers': {'SPEAKER_00': {'display_name': 'Unknown', 'gender': 'unknown'}}, 'relationships': []}
            with patch.object(llm_router, 'generate_completion', AsyncMock(return_value=json.dumps(profile))) as provider:
                analyzed = await agent_toolkit.execute('analyze_speaker_profiles', {'cues': transcribed['cues']})
                prompt = provider.await_args.args[1]
                assert set(analyzed['speakers']) == {'SPEAKER_00'} and 'Hello' not in prompt
                record('asr_to_profiles_loses_tags_and_text', observed_tags=['A', 'B'], returned_tags=list(analyzed['speakers']), prompt=prompt)

            rows = [{'source_speaker': 'A', 'target_speaker': 'B', 'self_pronoun': 'toi', 'target_pronoun': 'ban'}]
            with patch.object(llm_router, 'generate_completion', AsyncMock(return_value=json.dumps({'relationships': rows}))):
                matrix = await agent_toolkit.execute('build_relationship_matrix', {'speaker_profiles': {'A': {}, 'B': {}}, 'dialogue_context': 'A greets B'})
            try:
                await agent_toolkit.execute('translate_subtitle_chunk', {'cues': [{'id': 1, 'text': 'Hello', 'duration': 3}], 'relationship_matrix': matrix['relationships']})
            except ValueError as error:
                record('matrix_output_rejected_by_translation_schema', error_type=type(error).__name__)
            else:
                raise AssertionError('Relationship list unexpectedly accepted; update audit')

            with patch.object(llm_router, 'generate_completion', AsyncMock(return_value='{"translations":[{"id":1,"text":"Xin chao"}]}')):
                translated = await agent_toolkit.execute('translate_subtitle_chunk', {'source_lang': 'en', 'cues': [{'id': 1, 'text': 'Hello', 'duration': 3}]})
                assert translated['translations'][0]['translated_text'] == 'Xin chao'
                record('translation_service_happy_path', count=len(translated['translations']))

            invalid = await agent_toolkit.execute('run_subtitle_guardrails', {
                'requested_cues': [{'id': 1, 'text': 'Hello', 'duration': .1}],
                'llm_raw_response': '{"translations":[{"id":1,"text":"This is too fast"}]}',
            })
            assert not invalid['is_valid'] and invalid['total_passed'] == 1
            record('guardrails_counts_rejected_translation_as_passed', result=invalid)

            glossary = await agent_toolkit.execute('query_master_glossary', {'query': 'latency', 'source_lang': 'en', 'limit': 3})
            assert glossary['total_matches'] >= 1
            record('glossary_search', matches=glossary['total_matches'])

            exported = await agent_toolkit.execute('export_subtitles', {'cues': translated['translations'], 'format': 'ass', 'preset': 'cinema'})
            assert '[Script Info]' in exported['content'] and 'Xin chao' in exported['content']
            record('export_returns_content_without_file', fields=list(exported), has_subtitle_path='subtitle_path' in exported)

            with patch.object(tts_service, 'generate_preview', AsyncMock(return_value={'preview_url': '/static/previews/alice/example.mp3'})) as speech:
                dubbed = await agent_toolkit.execute('generate_dubbing_audio', {'text': 'Hello', 'voice': 'nova', 'speed': 1.2})
                assert speech.await_args.kwargs['custom_text'] == 'Hello'
                record('tts_preview_only', result=dubbed, call=speech.await_args.kwargs)

            # Ownership is enforced but active_job_id does not block the direct burn.
            with patch.object(video_burner, 'burn_subtitles_to_video', AsyncMock(return_value=output)) as burn:
                first = await agent_toolkit.execute('burn_video_subtitles', {'video_path': str(video), 'subtitle_path': str(subtitle), 'output_path': str(output), 'preset': 'cinema'})
                call_one = str(burn.await_args)
                second = await agent_toolkit.execute('burn_video_subtitles', {'video_path': str(video), 'subtitle_path': str(subtitle), 'output_path': str(output), 'preset': 'yellow_highlight'})
                assert str(burn.await_args) == call_one
                async with factory() as db:
                    stored = await db.get(Project, pid)
                    assert stored.active_job_id == 'existing-job' and stored.burned_video_url is None
                record('burn_bypasses_project_job_and_ignores_preset', status=second['status'], active_job='existing-job', project_output_url=None, media_call=call_one, returned_presets=[first['preset'], second['preset']])

            try:
                await agent_toolkit.execute('inspect_video_media', {'video_path': str(ROOT / 'README.md')})
            except ValueError:
                record('existing_foreign_path_denied', denied=True)
            else:
                raise AssertionError('Foreign path was not denied')

            missing = await agent_toolkit.execute_tool('inspect_video_media', {'video_path': str(directory / 'absent.mp4')})
            assert missing['success'] is True and missing['data']['status'] == 'ERROR'
            record('missing_media_wrapped_as_success', outer_success=missing['success'], inner_status=missing['data']['status'])

        # Valid JSON of an unexpected shape bypasses the JSONDecodeError handling.
        for raw in ('[]', '{"thought":"test","action":"query_master_glossary","action_input":[]}'):
            router = AsyncMock()
            router.generate_completion.return_value = raw
            try:
                await OneFLAgentRunner(router).run('Audit invalid response', max_iterations=1)
            except Exception as error:
                record('runner_unhandled_response_shape', raw=raw, exception=type(error).__name__)
            else:
                raise AssertionError('Runner shape validation changed; update audit')

        router = AsyncMock()
        router.generate_completion.side_effect = [
            '{"thought":"try","action":"unregistered_tool","action_input":{}}',
            '{"thought":"done","final_answer":"Finished successfully"}',
        ]
        result = await OneFLAgentRunner(router).run('Produce a video artifact', max_iterations=2)
        assert result.success and result.trajectory[0].is_error
        record('runner_final_success_is_model_assertion', success=result.success, prior_tool_error=result.trajectory[0].is_error)

        # Real HTTP routes, without entering lifespan or starting a worker.
        from fastapi.testclient import TestClient
        from app.main import app
        from app.agent.agent_runner import agent_runner
        client = TestClient(app, raise_server_exceptions=False)
        try:
            discovered = client.get('/api/v1/agent/tools')
            assert discovered.status_code == 200 and discovered.json()['total_tools'] == 10
            missing_http = client.post('/api/v1/agent/execute-tool', json={
                'tool_name': 'inspect_video_media', 'arguments': {'video_path': str(directory / 'absent.mp4')},
            })
            assert missing_http.status_code == 200 and missing_http.json()['success']
            assert missing_http.json()['result']['status'] == 'ERROR'
            record('http_tool_error_reported_as_success', http_status=missing_http.status_code, result=missing_http.json())
            with patch.object(agent_runner.llm_router, 'generate_completion', AsyncMock(return_value='[]')):
                failed = client.post('/api/v1/agent/chat', json={'goal': 'Inspect malformed provider output'})
            assert failed.status_code == 500
            record('http_chat_unexpected_json_shape_returns_500', http_status=failed.status_code, detail=failed.json())
            with patch.object(settings, 'API_ACCESS_TOKEN', 'audit-only-example-token-2026'):
                anonymous = client.get('/api/v1/agent/tools')
                authorized = client.get('/api/v1/agent/tools', headers={'Authorization': 'Bearer audit-only-example-token-2026'})
                assert anonymous.status_code == 401 and authorized.status_code == 200
                record('http_authentication_enforced', anonymous_status=anonymous.status_code, authenticated_status=authorized.status_code)
        finally:
            client.close()
    finally:
        current_user.reset(handle)
        await engine.dispose()
        (WORK / 'probe-results.json').write_text(json.dumps(observations, indent=2, ensure_ascii=False), encoding='utf-8')
    print('AUDIT OBSERVATIONS', len(observations))


if __name__ == '__main__':
    asyncio.run(main())
