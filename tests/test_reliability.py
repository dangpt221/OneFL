"""Behavior regressions for the 2026-10-21 audit; all providers are isolated."""

import json
from pathlib import Path
from unittest.mock import AsyncMock

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.config import settings
from app.database import Base
from app.models.project import Project
from app.services.asr_service import ASRService
from app.services.guardrails import SubtitleGuardrails
from app.services.llm_router import llm_router
from app.services.translation_service import translation_service
from app.services.video_burner import VideoBurner


@pytest_asyncio.fixture
async def isolated_db(tmp_path, monkeypatch):
    from app.services.storage_service import storage_service
    for attr, leaf in [('OUTPUT_DIR', 'outputs'), ('UPLOAD_DIR', 'uploads'), ('TEMP_SCRATCH_DIR', 'scratch')]:
        directory = tmp_path / leaf
        directory.mkdir()
        monkeypatch.setattr(settings, attr, directory)
    monkeypatch.setattr(storage_service, 'output_dir', settings.OUTPUT_DIR)
    monkeypatch.setattr(storage_service, 'scratch_dir', settings.TEMP_SCRATCH_DIR)
    test_engine = create_async_engine('sqlite+aiosqlite:///:memory:')
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(test_engine, expire_on_commit=False)
    async with factory() as db:
        yield db
    await test_engine.dispose()


def cue(index=1, **changes):
    return {'cue_index': index, 'original_text': 'Hello', 'start_time': 0., 'end_time': 5., **changes}


def response(*items):
    return json.dumps({'translations': [{'id': i, 'text': t} for i, t in items]})


def test_wrap_preserves_every_word_and_reports_excess_lines():
    text = ' '.join(['word'] * 40)
    valid, translations, violations = SubtitleGuardrails.validate_batch(
        [{'id': 1, 'text': 'source', 'duration': 30.}], response((1, text))
    )
    assert translations[0].text.split() == text.split()
    assert not valid
    assert any(v['type'] == 'TOO_MANY_LINES' for v in violations)


@pytest.mark.parametrize('items', [[(1, '')], [(1, 'a'), (1, 'b')], [(1, 'ok'), (99, 'extra')]])
def test_empty_duplicate_and_unknown_translation_ids_are_rejected(items):
    valid, _, violations = SubtitleGuardrails.validate_batch(
        [{'id': 1, 'text': 'source', 'duration': 3.}], response(*items)
    )
    assert not valid and violations


def test_db_relationship_list_enforces_pronouns():
    valid, _, violations = SubtitleGuardrails.validate_batch(
        [{'id': 1, 'text': 'Hey', 'duration': 4., 'speaker': 'A', 'target_speaker': 'B'}],
        response((1, 'Mày làm gì?')),
        [{'source_speaker': 'A', 'target_speaker': 'B', 'self_pronoun': 'Anh', 'target_pronoun': 'Em'}],
    )
    assert not valid
    assert any(v['type'] == 'PRONOUN_MISMATCH' for v in violations)


@pytest.mark.asyncio
async def test_translation_provider_failure_is_not_source_text_success(monkeypatch):
    monkeypatch.setattr(llm_router, 'generate_completion', AsyncMock(side_effect=RuntimeError('offline')))
    with pytest.raises(RuntimeError, match='offline'):
        await translation_service.translate_project_cues('audit', [cue()])


@pytest.mark.asyncio
async def test_reflexion_restores_missing_ids(monkeypatch):
    monkeypatch.setattr(llm_router, 'generate_completion', AsyncMock(side_effect=[
        'invalid json', response((1, 'Xin chào')),
    ]))
    result = await translation_service.translate_project_cues('audit', [cue()])
    assert result[0]['translated_text'] == 'Xin chào'


@pytest.mark.asyncio
async def test_unresolved_guardrail_violation_fails_batch(monkeypatch):
    monkeypatch.setattr(llm_router, 'generate_completion', AsyncMock(return_value=response((1, 'x' * 90))))
    with pytest.raises(RuntimeError, match='[Gg]uardrail|quality|validation'):
        await translation_service.translate_project_cues('audit', [cue()])


@pytest.mark.asyncio
async def test_force_translation_honors_model_temperature_and_preserves_manual_edits(monkeypatch):
    completion = AsyncMock(return_value=response((1, 'Bản mới')))
    monkeypatch.setattr(llm_router, 'generate_completion', completion)
    result = await translation_service.translate_project_cues(
        'audit', [cue(translated_text='old'), cue(2, translated_text='Manual', is_edited=True)],
        force_reprocess=True, model_override='test-model', temperature=0.2,
    )
    assert result[0]['translated_text'] == 'Bản mới'
    assert result[1]['translated_text'] == 'Manual'
    assert completion.call_args.kwargs['model_override'] == 'test-model'
    assert completion.call_args.kwargs['temperature'] == 0.2


@pytest.mark.asyncio
async def test_translation_checkpoint_failure_propagates(monkeypatch):
    monkeypatch.setattr(llm_router, 'generate_completion', AsyncMock(return_value=response((1, 'Xin chào'))))
    with pytest.raises(RuntimeError, match='database unavailable'):
        await translation_service.translate_project_cues(
            'audit', [cue()], batch_callback=AsyncMock(side_effect=RuntimeError('database unavailable'))
        )


@pytest.mark.asyncio
async def test_asr_loading_failure_is_not_demo_content(tmp_path, monkeypatch):
    service = ASRService()
    audio = tmp_path / 'input.wav'
    audio.write_bytes(b'nonempty')
    monkeypatch.setattr(service, '_get_or_load_model', lambda: (_ for _ in ()).throw(RuntimeError('model failed')))
    with pytest.raises(RuntimeError, match='model failed'):
        await service.transcribe_audio(audio)


@pytest.mark.asyncio
async def test_asr_missing_input_is_explicit_failure(tmp_path):
    with pytest.raises((FileNotFoundError, ValueError)):
        await ASRService().transcribe_audio(tmp_path / 'missing.wav')


@pytest.mark.asyncio
async def test_burn_failure_never_copies_source(tmp_path, monkeypatch):
    burner = VideoBurner()
    source = tmp_path / 'source.mp4'
    source.write_bytes(b'original')
    ass = tmp_path / 'test.ass'
    ass.write_text('invalid ASS')
    process = AsyncMock()
    process.returncode = 1
    process.communicate.return_value = (b'', b'encode failed')
    monkeypatch.setattr(burner, 'detect_best_encoder', AsyncMock(return_value='libx264'))
    monkeypatch.setattr('asyncio.create_subprocess_exec', AsyncMock(return_value=process))
    with pytest.raises(RuntimeError):
        await burner.burn_subtitles_to_video(source, ass, tmp_path / 'burned.mp4')
    assert not (tmp_path / 'burned.mp4').exists()


@pytest.mark.asyncio
async def test_empty_concat_cannot_be_success(tmp_path):
    with pytest.raises(ValueError):
        await VideoBurner().lossless_concat_chunks([], tmp_path / 'out.mp4')


@pytest.mark.asyncio
async def test_pipeline_keeps_media_duration(isolated_db, tmp_path, monkeypatch):
    from app.services.workflow_engine import workflow_engine
    from app.services.asr_service import asr_service
    from app.services.translation_service import translation_service
    from app.services.speaker_profiler import speaker_profiler
    video = tmp_path / 'source.mp4'
    video.write_bytes(b'video')
    audio = tmp_path / 'audio.wav'
    audio.write_bytes(b'audio')
    project = Project(title='audit', local_video_path=str(video), extracted_audio_path=str(audio), video_duration_seconds=12.)
    isolated_db.add(project)
    await isolated_db.commit()
    monkeypatch.setattr(asr_service, 'get_audio_duration', lambda p: 12.)
    monkeypatch.setattr(asr_service, 'transcribe_audio', AsyncMock(return_value=[cue(end_time=4.)]))
    monkeypatch.setattr(speaker_profiler, 'analyze_speakers_and_matrix', AsyncMock(return_value={'speakers': {}, 'relationships': []}))
    monkeypatch.setattr(translation_service, 'translate_project_cues', AsyncMock(return_value=[cue(translated_text='Xin chào')]))
    await workflow_engine.run_pipeline(isolated_db, project.id, start_stage='ASR_PROCESSING')
    assert project.video_duration_seconds == 12.
    assert project.status == 'WAITING_REVIEW'
