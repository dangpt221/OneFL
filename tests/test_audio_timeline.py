import struct
import wave
from pathlib import Path
from unittest.mock import AsyncMock

import pytest


@pytest.mark.asyncio
async def test_synthesis_failure_is_never_silent_success(tmp_path, monkeypatch):
    from app.services.tts_service import tts_service
    monkeypatch.setattr('edge_tts.Communicate.save', AsyncMock(side_effect=RuntimeError('network failed')))
    with pytest.raises(RuntimeError):
        await tts_service.synthesize_speech('Xin chào', output_path=tmp_path / 'voice.mp3')


@pytest.mark.asyncio
async def test_timeline_mixer_preserves_overlap_with_bounded_blocks(tmp_path):
    from app.services.pcm_mixer import mix_pcm_blocks
    first, second, output = tmp_path / 'first.pcm', tmp_path / 'second.pcm', tmp_path / 'out.pcm'
    first.write_bytes(struct.pack('<4h', 1000, 1000, 1000, 1000))
    second.write_bytes(struct.pack('<2h', 2000, 2000))
    mix_pcm_blocks([(0, first), (2, second)], output, total_samples=6, block_samples=2)
    assert struct.unpack('<6h', output.read_bytes()) == (1000, 1000, 3000, 3000, 0, 0)


@pytest.mark.asyncio
async def test_dubbing_rejects_missing_speech_instead_of_source_fallback(tmp_path, monkeypatch):
    from app.services.tts_service import tts_service
    monkeypatch.setattr(tts_service, 'synthesize_speech', AsyncMock(side_effect=RuntimeError('voice failed')))
    with pytest.raises(RuntimeError, match='voice failed'):
        await tts_service.dub_project_timeline([
            {'cue_index': 1, 'start_time': 0., 'end_time': 1., 'translated_text': 'Xin chào'}
        ], 2., tmp_path / 'dubbed.mp3')
