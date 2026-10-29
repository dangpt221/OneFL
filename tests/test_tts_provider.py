"""Configured TTS defaults and safe provider failures without external speech calls."""
import asyncio
from pathlib import Path
from unittest.mock import AsyncMock

import aiohttp
import pytest
from fastapi import HTTPException

from app.config import settings
from app.services import tts_service as tts_module
from app.services.tts_service import VOICE_CATALOG, tts_service
from tests.test_reliability import isolated_db


def handshake_error(status=403):
    from multidict import CIMultiDictProxy, CIMultiDict
    from yarl import URL
    secret_url = URL('https://speech.example.test/ws?token=PRIVATE-TOKEN')
    info = aiohttp.RequestInfo(secret_url, 'GET', CIMultiDictProxy(CIMultiDict()), secret_url)
    return aiohttp.WSServerHandshakeError(info, (), status=status, message='Invalid response status')


def test_catalog_marks_only_configured_default_without_mutating_catalog(monkeypatch):
    original = [voice.copy() for voice in VOICE_CATALOG]
    monkeypatch.setattr(settings, 'DEFAULT_TTS_VOICE', 'vieneu-ngoc-huyen')
    first = tts_service.get_voices()
    assert [voice['id'] for voice in first if voice['is_default']] == ['vieneu-ngoc-huyen']
    monkeypatch.setattr(settings, 'DEFAULT_TTS_VOICE', 'vi-VN-NamMinhNeural')
    assert [voice['id'] for voice in tts_service.get_voices() if voice['is_default']] == ['vi-VN-NamMinhNeural']
    assert VOICE_CATALOG == original


@pytest.mark.asyncio
async def test_omitted_service_voice_uses_current_setting(isolated_db, monkeypatch):
    from app.services import media_process
    import edge_tts
    monkeypatch.setattr(settings, 'DEFAULT_TTS_VOICE', 'vi-VN-NamMinhNeural')
    monkeypatch.setattr(media_process, 'probe_media', AsyncMock(return_value=1.))
    communicate = []

    class Speech:
        def __init__(self, text, **kwargs):
            communicate.append(kwargs)

        async def save(self, path):
            Path(path).write_bytes(b'local speech fixture')

    monkeypatch.setattr(edge_tts, 'Communicate', Speech)
    output = settings.OUTPUT_DIR / 'default.mp3'
    assert await tts_service.synthesize_speech('Hello', output_path=output) == output
    assert communicate == [{'voice': 'vi-VN-NamMinhNeural', 'rate': '+0%', 'pitch': '+0Hz'}]


@pytest.mark.asyncio
async def test_preview_default_is_resolved_before_synthesis_and_cache(isolated_db, monkeypatch):
    from app.services import media_process
    monkeypatch.setattr(settings, 'DEFAULT_TTS_VOICE', 'vieneu-ngoc-huyen')
    monkeypatch.setattr(media_process, 'probe_media', AsyncMock(return_value=1.))
    requested = []

    async def speech(text, **kwargs):
        requested.append(kwargs['voice'])
        kwargs['output_path'].write_bytes(b'local speech fixture')

    monkeypatch.setattr(tts_service, 'synthesize_speech', speech)
    first = await tts_service.generate_preview(custom_text='Hello')
    again = await tts_service.generate_preview(custom_text='Hello')
    explicit = await tts_service.generate_preview('vi-VN-NamMinhNeural', custom_text='Hello')
    assert first['voice_id'] == 'vieneu-ngoc-huyen'
    assert first['preview_url'] == again['preview_url'] != explicit['preview_url']
    assert requested == ['vieneu-ngoc-huyen', 'vi-VN-NamMinhNeural']


@pytest.mark.asyncio
async def test_timeline_omitted_voice_is_current_setting(isolated_db, monkeypatch):
    monkeypatch.setattr(settings, 'DEFAULT_TTS_VOICE', 'vieneu-ngoc-huyen')
    speech = AsyncMock(side_effect=RuntimeError('stop before media generation'))
    monkeypatch.setattr(tts_service, 'synthesize_speech', speech)
    with pytest.raises(RuntimeError, match='stop before media'):
        await tts_service.dub_project_timeline([
            {'cue_index': 1, 'start_time': 0, 'end_time': 1, 'translated_text': 'Hello'},
        ], 1., settings.OUTPUT_DIR / 'dubbed.mp3')
    assert speech.await_args.args[1] == 'vieneu-ngoc-huyen'


@pytest.mark.asyncio
async def test_terminal_edge_403_is_safe_typed_error_without_voice_fallback(tmp_path, monkeypatch):
    import edge_tts
    provider_error = getattr(tts_module, 'TTSProviderError', RuntimeError)
    save = AsyncMock(side_effect=handshake_error())
    communicate = []

    class Speech:
        def __init__(self, text, **kwargs):
            communicate.append(kwargs)

    Speech.save = save

    monkeypatch.setattr(edge_tts, 'Communicate', Speech)
    output = tmp_path / 'speech.mp3'
    with pytest.raises(provider_error) as caught:
        await tts_service.synthesize_speech('Hello', voice='vieneu-ngoc-huyen', output_path=output)
    assert type(caught.value).__name__ == 'TTSProviderError'
    assert '403' in str(caught.value) and '7.3.1' in str(caught.value)
    assert 'PRIVATE-TOKEN' not in str(caught.value) and 'https://' not in str(caught.value)
    assert save.await_count == 1
    assert communicate == [{'voice': 'vi-VN-HoaiMyNeural', 'rate': '+12%', 'pitch': '-32Hz'}]
    assert not output.exists() and not list(tmp_path.glob('*.mp3'))
    assert caught.value.__cause__.status == 403


@pytest.mark.asyncio
async def test_transient_edge_failure_retries_same_voice_and_cleans_partial(tmp_path, monkeypatch):
    import edge_tts
    provider_error = getattr(tts_module, 'TTSProviderError', RuntimeError)
    voices = []

    class Speech:
        def __init__(self, text, **kwargs):
            voices.append(kwargs['voice'])

        async def save(self, path):
            Path(path).write_bytes(b'partial')
            raise aiohttp.ClientConnectionError('private diagnostic')

    monkeypatch.setattr(edge_tts, 'Communicate', Speech)
    monkeypatch.setattr(tts_module.asyncio, 'sleep', AsyncMock())
    with pytest.raises(provider_error) as caught:
        await tts_service.synthesize_speech('Hello', voice='vi-VN-NamMinhNeural', output_path=tmp_path / 'speech.mp3')
    assert type(caught.value).__name__ == 'TTSProviderError'
    assert voices == ['vi-VN-NamMinhNeural'] * 3
    assert 'private diagnostic' not in str(caught.value)
    assert not list(tmp_path.glob('*.mp3'))


@pytest.mark.asyncio
async def test_cancellation_propagates_without_retry_or_partial_output(tmp_path, monkeypatch):
    async def cancelled(path):
        Path(path).write_bytes(b'partial')
        raise asyncio.CancelledError()

    save = AsyncMock(side_effect=cancelled)
    monkeypatch.setattr('edge_tts.Communicate.save', save)
    with pytest.raises(asyncio.CancelledError):
        await tts_service.synthesize_speech('Hello', voice='vieneu-ngoc-huyen', output_path=tmp_path / 'speech.mp3')
    assert save.await_count == 1
    assert not list(tmp_path.glob('*.mp3'))


@pytest.mark.asyncio
async def test_preview_schema_default_and_typed_provider_failure(monkeypatch):
    from app.api.v1.tts import TTSPreviewRequest, preview_voice
    monkeypatch.setattr(settings, 'DEFAULT_TTS_VOICE', 'vieneu-ngoc-huyen')
    assert TTSPreviewRequest().voice == 'vieneu-ngoc-huyen'
    assert TTSPreviewRequest(voice='vi-VN-NamMinhNeural').voice == 'vi-VN-NamMinhNeural'
    provider_error = getattr(tts_module, 'TTSProviderError', RuntimeError)
    failure = provider_error('Microsoft Edge unavailable; retry with the same selected voice')
    monkeypatch.setattr(tts_service, 'generate_preview', AsyncMock(side_effect=failure))
    with pytest.raises(HTTPException) as caught:
        await preview_voice(TTSPreviewRequest())
    assert caught.value.status_code == 502
    assert caught.value.detail == str(failure)


@pytest.mark.asyncio
async def test_unknown_voice_remains_invalid_input(monkeypatch):
    from app.api.v1.tts import TTSPreviewRequest, preview_voice
    monkeypatch.setattr('edge_tts.Communicate.save', AsyncMock(side_effect=AssertionError('must not call provider')))
    with pytest.raises(ValueError, match='Unknown voice ID'):
        await preview_voice(TTSPreviewRequest(voice='unknown-voice'))


@pytest.mark.asyncio
async def test_preview_http_error_is_actionable_and_unknown_voice_is_422(isolated_db, monkeypatch, caplog):
    from httpx import ASGITransport, AsyncClient
    from app.main import app
    monkeypatch.setattr(settings, 'API_ACCESS_TOKEN', None)
    monkeypatch.setattr(settings, 'AUTH_USERS', {})
    monkeypatch.setattr(settings, 'ENV', 'development')
    save = AsyncMock(side_effect=handshake_error())
    monkeypatch.setattr('edge_tts.Communicate.save', save)
    async with AsyncClient(transport=ASGITransport(app=app, client=('127.0.0.1', 12345)),
                           base_url='http://127.0.0.1') as client:
        response = await client.post('/api/v1/tts/preview', json={'voice': 'vieneu-ngoc-huyen'})
        assert response.status_code == 502
        assert 'Microsoft Edge' in response.json()['detail'] and '7.3.1' in response.json()['detail']
        assert 'PRIVATE-TOKEN' not in response.text
        response = await client.post('/api/v1/tts/preview', json={'voice': 'unknown-voice'})
        assert response.status_code == 422
    assert save.await_count == 1
    assert 'WSServerHandshakeError' in caplog.text
    assert not list(settings.OUTPUT_DIR.rglob('*.mp3'))


@pytest.mark.asyncio
async def test_openai_failure_is_typed_without_using_another_provider(tmp_path, monkeypatch):
    import httpx
    import openai
    from types import SimpleNamespace
    from app.services.tts_service import TTSProviderError
    monkeypatch.setattr(settings, 'OPENAI_API_KEY', 'private-test-key')
    request = httpx.Request('POST', 'https://speech.example.test/private')
    failure = openai.AuthenticationError('private diagnostics', response=httpx.Response(401, request=request), body={})
    speech = AsyncMock(side_effect=failure)

    class Client:
        def __init__(self, **kwargs):
            self.audio = SimpleNamespace(speech=SimpleNamespace(create=speech))

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

    edge = AsyncMock(side_effect=AssertionError('No alternate provider'))
    monkeypatch.setattr(openai, 'AsyncOpenAI', Client)
    monkeypatch.setattr('edge_tts.Communicate.save', edge)
    with pytest.raises(TTSProviderError) as caught:
        await tts_service.synthesize_speech('Hello', voice='nova', output_path=tmp_path / 'speech.mp3')
    assert 'OpenAI' in str(caught.value) and 'private' not in str(caught.value)
    assert caught.value.__cause__ is failure
    assert speech.await_count == 1 and edge.await_count == 0
    assert not list(tmp_path.glob('*.mp3'))


@pytest.mark.asyncio
async def test_google_failure_is_typed_and_preserves_selected_provider(tmp_path, monkeypatch):
    import gtts
    from gtts.tts import gTTSError
    from app.services.tts_service import TTSProviderError
    calls = []

    class Speech:
        def __init__(self, **kwargs):
            calls.append(kwargs)

        def save(self, path):
            raise gTTSError(msg='private provider details')

    edge = AsyncMock(side_effect=AssertionError('No alternate provider'))
    monkeypatch.setattr(gtts, 'gTTS', Speech)
    monkeypatch.setattr('edge_tts.Communicate.save', edge)
    with pytest.raises(TTSProviderError) as caught:
        await tts_service.synthesize_speech('Hello', voice='gtts-female-vi', output_path=tmp_path / 'speech.mp3')
    assert 'Google' in str(caught.value) and 'private' not in str(caught.value)
    assert len(calls) == 1 and edge.await_count == 0
    assert not list(tmp_path.glob('*.mp3'))


@pytest.mark.asyncio
async def test_local_media_failure_is_not_retried_as_provider_failure(tmp_path, monkeypatch):
    from app.services import media_process
    from app.services.tts_service import TTSProviderError

    async def save(path):
        Path(path).write_bytes(b'invalid audio fixture')

    provider = AsyncMock(side_effect=save)
    monkeypatch.setattr('edge_tts.Communicate.save', provider)
    monkeypatch.setattr(media_process, 'probe_media', AsyncMock(side_effect=RuntimeError('Invalid media streams')))
    with pytest.raises(RuntimeError, match='Invalid media streams') as caught:
        await tts_service.synthesize_speech('Hello', voice='vi-VN-NamMinhNeural', output_path=tmp_path / 'speech.mp3')
    assert not isinstance(caught.value, TTSProviderError)
    assert provider.await_count == 1
    assert not list(tmp_path.glob('*.mp3'))
