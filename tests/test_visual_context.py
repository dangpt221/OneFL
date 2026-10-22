import base64
import pytest
from unittest.mock import AsyncMock


@pytest.mark.asyncio
async def test_visual_context_requires_real_frames_and_valid_response(tmp_path, monkeypatch):
    from app.services.visual_context import visual_context_service
    from app.config import settings
    monkeypatch.setattr(settings, 'OPENAI_API_KEY', 'test-key')
    frame = base64.b64encode(b'jpeg').decode()
    call = AsyncMock(return_value='{"context":"A speaker at a conference"}')
    monkeypatch.setattr(visual_context_service, '_request', call)
    result = await visual_context_service.describe_frames([frame])
    assert result == 'A speaker at a conference'
    assert call.call_args.args[0] == [frame]
    with pytest.raises(ValueError):
        await visual_context_service.describe_frames([])
