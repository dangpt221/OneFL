"""Isolated full-stack fixture server. External providers only are replaced.

Run manually: backend/.venv/Scripts/python.exe tests/e2e_backend.py
Never import this module from the production application.
"""
import asyncio
import json
import os
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
WORK = ROOT / 'tmp' / 'feature-audit' / 'runtime'
WORK.mkdir(parents=True, exist_ok=True)
os.environ.update({
    'DATABASE_URL': 'sqlite+aiosqlite:///' + (WORK / 'e2e.db').as_posix(),
    'OUTPUT_DIR': str(WORK / 'outputs'), 'UPLOAD_DIR': str(WORK / 'uploads'),
    'TEMP_SCRATCH_DIR': str(WORK / 'scratch'), 'ENV': 'development', 'DEBUG': 'false',
    'STORAGE_DRIVER': 'local', 'API_ACCESS_TOKEN': 'onefl-browser-fixture-access-2026', 'AUTH_USERS': '{}',
    'CORS_ORIGINS': '["http://127.0.0.1:3100","http://localhost:3100"]',
    'GEMINI_API_KEY': '', 'OPENAI_API_KEY': '', 'HF_TOKEN': '',
    'ENABLE_SPEAKER_PROFILER': 'false', 'ENABLE_SPEAKER_DIARIZATION': 'false',
    'ENABLE_VISUAL_CONTEXT': 'false', 'JOB_POLL_SECONDS': '0.2',
})
sys.path.insert(0, str(ROOT / 'backend'))

from app.main import app
from app.config import settings
from app.services.media_process import run_media
from app.services.asr_service import asr_service
from app.services.llm_router import llm_router
from app.services.tts_service import tts_service
from app.services.video_burner import video_burner
from app.services.video_downloader import video_downloader
from fastapi import HTTPException, Request

control = {'fail_translation': False, 'fail_tts': False, 'delay': 1.0, 'speech_calls': []}
video_burner._cached_encoder = 'libx264'


async def fixture_asr(*args, progress_callback=None, **kwargs):
    await asyncio.sleep(control['delay'])
    if progress_callback:
        await progress_callback(100, 'Fixture ASR complete')
    return [dict(cue_index=i + 1, start_time=start, end_time=end, original_text=text, speaker_tag='SPEAKER_00')
            for i, (start, end, text) in enumerate([(.1, 1.3, 'Hello'), (1.5, 2.8, 'Goodbye')])]


async def fixture_completion(system_prompt, user_prompt, **kwargs):
    await asyncio.sleep(control['delay'])
    if control['fail_translation']:
        raise RuntimeError('Fixture provider unavailable')
    ids = sorted(set(map(int, re.findall(r'"id"\s*:\s*(\d+)', user_prompt))))
    return json.dumps({'translations': [{'id': i, 'text': 'Xin chao' if i % 2 else 'Tam biet'} for i in ids]})


async def fixture_speech(text, voice='vi-VN-HoaiMyNeural', model='tts-1', speed=1., output_path=None):
    if control['fail_tts']:
        raise RuntimeError('Fixture speech provider unavailable')
    control['speech_calls'].append({'text': text, 'voice': voice, 'model': model, 'speed': speed})
    await run_media([settings.get_ffmpeg_bin(), '-y', '-f', 'lavfi', '-i', 'sine=frequency=700:sample_rate=24000', '-t', '0.4', str(output_path)])
    return output_path


async def fixture_url_info(url):
    return dict(success=True, title='Fixture URL video', duration=3, platform='bilibili', suggested_source_language='zh', url=url, thumbnail='', uploader='fixture')


async def fixture_download(url, output_dir, progress_callback=None):
    from shutil import copyfile
    await asyncio.sleep(control['delay'])
    target = Path(output_dir) / 'downloaded.mp4'
    copyfile(WORK / 'source.mp4', target)
    if progress_callback:
        await progress_callback({'pct': 100})
    return {'file_path': target, 'duration': 3., 'title': 'Fixture URL video'}


asr_service.transcribe_audio = fixture_asr
llm_router.generate_completion = fixture_completion
tts_service.synthesize_speech = fixture_speech
video_downloader.extract_info = fixture_url_info
video_downloader.download_video = fixture_download


@app.post('/__e2e/control')
async def configure(request: Request):
    if request.headers.get('x-e2e-key') != 'onefl-browser-fixture-access-2026':
        raise HTTPException(403)
    changes = await request.json()
    if changes.get('seed_project_id'):
        from app.database import get_async_session
        from app.models.project import Project
        from app.models.subtitle import SubtitleCue
        count = int(changes.get('seed_count', 1000))
        if not 1 <= count <= 10000:
            raise HTTPException(422, 'Fixture count must be 1..10000')
        async with get_async_session() as db:
            project = await db.get(Project, changes['seed_project_id'])
            if not project or project.active_job_id:
                raise HTTPException(409, 'Seed only a new idle fixture project')
            from sqlalchemy import func, select
            if await db.scalar(select(func.count(SubtitleCue.id)).where(SubtitleCue.project_id == project.id)):
                raise HTTPException(409, 'Seed requires an empty fixture project')
            db.add_all([SubtitleCue(project_id=project.id, cue_index=i + 1, start_time=i * 3., end_time=i * 3. + 2.,
                original_text=f'Source line {i}', translated_text=f'Target line {i}', speaker_tag='SPEAKER_00') for i in range(count)])
            project.status, project.current_stage = 'WAITING_REVIEW', 'WAITING_REVIEW'
            project.content_revision += 1
            await db.commit()
        return {'seeded': count}
    for key in ('fail_translation', 'fail_tts', 'delay'):
        if key in changes:
            control[key] = changes[key]
    return control


if __name__ == '__main__':
    (WORK / 'server.pid').write_text(str(os.getpid()))
    import uvicorn
    async def prepare():
        await run_media([settings.get_ffmpeg_bin(), '-y', '-f', 'lavfi', '-i', 'testsrc=size=320x240:rate=15',
                         '-f', 'lavfi', '-i', 'sine=frequency=440:sample_rate=24000', '-t', '3',
                         '-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-c:a', 'aac', str(WORK / 'source.mp4')])
    asyncio.run(prepare())
    uvicorn.run(app, host='127.0.0.1', port=int(os.environ.get('ONEFL_E2E_PORT', '8100')))
