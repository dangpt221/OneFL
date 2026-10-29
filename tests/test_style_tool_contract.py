"""Style selection survives HTTP/Agent export and durable burn admission."""
from pathlib import Path

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.agent.tools import agent_toolkit
from app.database import get_db
from app.models.job import Job
from app.models.project import Project
from app.models.subtitle import SubtitleCue
from tests.test_agent_completion import wire_sessions
from tests.test_reliability import isolated_db


def assert_comic(content: str) -> None:
    style = next(line for line in content.splitlines() if line.startswith('Style: Default,'))
    fields = style.removeprefix('Style: ').split(',')
    assert fields[8] == '1'  # Italic accompanies the bold white/black-outline preset.
    assert 'XIN CHÀO' in content


@pytest.mark.asyncio
async def test_agent_standalone_comic_export_uses_actual_style():
    result = await agent_toolkit.execute('export_subtitles', {
        'preset': 'comic',
        'cues': [{'start_time': 0, 'end_time': 2, 'original_text': 'Hello',
                  'translated_text': 'Xin chào'}],
    })
    assert_comic(result['content'])


@pytest.mark.asyncio
async def test_agent_project_comic_export_is_persisted(isolated_db, monkeypatch):
    wire_sessions(isolated_db, monkeypatch)
    project = Project(title='Comic export')
    isolated_db.add(project)
    await isolated_db.flush()
    isolated_db.add(SubtitleCue(project_id=project.id, cue_index=1, start_time=0, end_time=2,
                                original_text='Hello', translated_text='Xin chào'))
    await isolated_db.commit()
    result = await agent_toolkit.execute('export_subtitles', {'project_id': project.id, 'preset': 'comic'})
    artifact = Path(result['subtitle_path'])
    assert_comic(artifact.read_text(encoding='utf-8'))
    await isolated_db.refresh(project)
    assert project.subtitles_ass_path == str(artifact)
    assert result['content_revision'] == project.content_revision


@pytest.mark.asyncio
async def test_agent_white_bar_burn_retains_mode_in_durable_job(isolated_db, monkeypatch):
    import av
    from app.config import settings
    from app.services.job_service import JobService
    from app.services.media_process import probe_media, run_media
    from app.services.video_burner import video_burner
    wire_sessions(isolated_db, monkeypatch)
    monkeypatch.setattr(video_burner, '_cached_encoder', 'libx264')
    project = Project(title='White bars')
    isolated_db.add(project)
    await isolated_db.flush()
    directory = settings.OUTPUT_DIR / project.id
    directory.mkdir()
    video = directory / 'source.mp4'
    await run_media([settings.get_ffmpeg_bin(), '-y', '-v', 'error', '-f', 'lavfi', '-i',
                     'color=c=0x225566:s=320x240:r=15:d=1.2', '-f', 'lavfi', '-i',
                     'sine=frequency=440:duration=1.2', '-c:v', 'libx264', '-pix_fmt',
                     'yuv420p', '-c:a', 'aac', '-shortest', str(video)])
    project.local_video_path = str(video)
    isolated_db.add(SubtitleCue(project_id=project.id, cue_index=1, start_time=0, end_time=1,
                                original_text='Hello', translated_text='Xin chào'))
    await isolated_db.commit()
    await agent_toolkit.execute('export_subtitles', {'project_id': project.id, 'preset': 'comic'})
    queued = await agent_toolkit.execute('burn_video_subtitles', {
        'project_id': project.id, 'clean_chinese_mode': 'white_bars',
    })
    assert queued['status'] == 'QUEUED'
    job = await isolated_db.get(Job, queued['job_id'])
    assert job.kind == 'AGENT_TOOL'
    assert job.payload['arguments']['clean_chinese_mode'] == 'white_bars'
    assert not Path(job.payload['arguments']['output_path']).exists()
    job.status = 'RUNNING'
    await isolated_db.commit()
    await JobService()._execute(job.id)
    finished = await agent_toolkit.execute('get_job_status', {'project_id': project.id, 'job_id': job.id})
    assert finished['status'] == 'SUCCEEDED', finished['error']
    assert finished['artifact_current']
    output = Path(finished['result']['output_path'])
    assert await probe_media(output, require_video=True, require_audio=True) == pytest.approx(1.2, abs=.15)
    with av.open(str(output)) as container:
        frame = next(container.decode(video=0)).to_ndarray(format='rgb24')
    assert frame.shape == (240, 320, 3)
    assert frame[2:12, 10:310].mean() > 245
    assert frame[230:238, 10:310].mean() > 245
    assert frame[90:140, 50:270].mean() < 130


@pytest.mark.asyncio
async def test_http_comic_export_keeps_same_style(isolated_db):
    from app.api.v1.subtitles import router
    project = Project(title='HTTP style')
    isolated_db.add(project)
    await isolated_db.flush()
    isolated_db.add(SubtitleCue(project_id=project.id, cue_index=1, start_time=0, end_time=2,
                                original_text='Hello', translated_text='Xin chào'))
    await isolated_db.commit()
    app = FastAPI()
    app.include_router(router)

    async def session():
        yield isolated_db

    app.dependency_overrides[get_db] = session
    async with AsyncClient(transport=ASGITransport(app=app), base_url='http://test') as client:
        response = await client.get(f'/projects/{project.id}/subtitles/export/ass?preset=comic')
        assert response.status_code == 200
        assert_comic(response.text)
