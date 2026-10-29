"""Optional visual context from bounded, real video frame samples.

Request format: https://developers.openai.com/api/docs/guides/images-vision
"""
import base64
import json
import tempfile
from pathlib import Path
import httpx
from pydantic import BaseModel, Field
from app.config import settings
from app.services.media_process import run_media


class VisualDescription(BaseModel):
    context: str = Field(min_length=1, max_length=4000)


class VisualContextService:
    async def describe_frames(self, frames: list[str]) -> str:
        if not 1 <= len(frames) <= 3 or any(len(frame) > 1024 * 1024 for frame in frames):
            raise ValueError('Visual context requires 1–3 bounded JPEG frames')
        if not settings.OPENAI_API_KEY or 'DIEN_API_KEY' in settings.OPENAI_API_KEY:
            raise RuntimeError('Visual context requires a configured vision-capable OpenAI provider')
        return VisualDescription.model_validate_json(await self._request(frames)).context

    async def _request(self, frames: list[str]) -> str:
        async with httpx.AsyncClient(timeout=settings.LLM_TIMEOUT_SECONDS) as client:
            response = await client.post(settings.OPENAI_API_BASE.rstrip('/') + '/chat/completions',
                headers={'Authorization': f'Bearer {settings.OPENAI_API_KEY}'}, json={
                    'model': settings.OPENAI_MODEL, 'response_format': {'type': 'json_object'},
                    'messages': [{'role': 'user', 'content': [
                        {'type': 'text', 'text': 'Describe visible setting, objects, actions and interpersonal cues for subtitle translation. Do not invent identities or dialogue. Return JSON {"context":"..."}.'},
                        *[{'type': 'image_url', 'image_url': {'url': f'data:image/jpeg;base64,{frame}', 'detail': 'low'}} for frame in frames],
                    ]}],
                })
            response.raise_for_status()
            return response.json()['choices'][0]['message']['content']

    async def describe_video(self, video: Path, times: list[float]) -> str:
        if not video.is_file():
            raise FileNotFoundError('Video for visual context is missing')
        frames = []
        with tempfile.TemporaryDirectory(prefix='vision_', dir=settings.TEMP_SCRATCH_DIR) as work:
            for index, timestamp in enumerate(times[:3]):
                output = Path(work) / f'{index}.jpg'
                await run_media([settings.get_ffmpeg_bin(), '-y', '-ss', str(max(0., timestamp)), '-i', str(video), '-frames:v', '1', '-vf', 'scale=640:-2', str(output)], timeout=60)
                if not output.exists() or output.stat().st_size > 768 * 1024:
                    raise RuntimeError('Video frame extraction failed or exceeded size limit')
                frames.append(base64.b64encode(output.read_bytes()).decode())
        return await self.describe_frames(frames)


visual_context_service = VisualContextService()
