"""Cue-window synchronization with real media, isolated DB and tone providers."""
import json

import numpy as np
import pytest
from fastapi import HTTPException

from app.config import settings
from app.models.project import Project
from app.models.subtitle import SubtitleCue
from app.services.media_process import run_media
from app.services.storage_service import storage_service
from app.services.tts_service import tts_service
from tests.test_reliability import isolated_db


@pytest.mark.asyncio
@pytest.mark.parametrize('last', [False, True])
async def test_speech_stays_inside_own_cue_and_reports_measured_duration(isolated_db, tmp_path, monkeypatch, last):
    async def tone(text, voice, model, speed, output_path):
        await run_media([settings.get_ffmpeg_bin(), '-y', '-f', 'lavfi', '-i',
                         'sine=frequency=880:sample_rate=24000', '-t', '1.8' if text == 'first' else '0.2', str(output_path)])
        return output_path
    monkeypatch.setattr(tts_service, 'synthesize_speech', tone)
    cues = [{'cue_index': 1, 'start_time': 1., 'end_time': 2., 'translated_text': 'first'}]
    if not last:
        cues.append({'cue_index': 2, 'start_time': 4., 'end_time': 4.5, 'translated_text': 'second'})
    output = tmp_path / 'speech.mp3'
    await tts_service.dub_project_timeline(cues, 5., output)
    decoded = tmp_path / 'decoded.pcm'
    await run_media([settings.get_ffmpeg_bin(), '-y', '-i', str(output), '-ar', '24000', '-ac', '1', '-f', 's16le', str(decoded)])
    samples = np.fromfile(decoded, dtype='<i2').astype(np.float64)
    assert np.sqrt(np.mean(samples[24000:36000] ** 2)) > 1000
    assert np.sqrt(np.mean(samples[50000:70000] ** 2)) < 20, 'Speech continues after subtitle end'
    report = json.loads(output.with_suffix('.timing.json').read_text(encoding='utf-8'))
    first = report['cues'][0]
    assert first['source_duration'] == pytest.approx(1.8, abs=.02)
    assert first['audio_end'] <= 2.
    assert 1.75 <= first['speedup'] <= 2.
    assert report['cue_count'] == len(cues)
    if not last:
        from app.services.subtitle_generator import subtitle_generator
        from app.services.video_burner import VideoBurner
        source, burned, muxed = tmp_path / 'source.mp4', tmp_path / 'burned.mp4', tmp_path / 'fixed.mp4'
        await run_media([settings.get_ffmpeg_bin(), '-y', '-f', 'lavfi', '-i', 'color=c=black:size=320x240:rate=25',
                         '-t', '5', '-c:v', 'libx264', str(source)])
        subtitle = tmp_path / 'fixed.ass'
        subtitle.write_text(subtitle_generator.generate_ass(cues), encoding='utf-8')
        burner = VideoBurner()
        burner._cached_encoder = 'libx264'
        await burner.burn_subtitles_to_video(source, subtitle, burned, mask_original_sub=False, clean_chinese_mode='none')
        await tts_service.mix_dubbed_video(burned, output, muxed, mix_original=False)
        await run_media([settings.get_ffmpeg_bin(), '-y', '-i', str(muxed), '-vn', '-ar', '24000', '-ac', '1', '-f', 's16le', str(decoded)])
        samples = np.fromfile(decoded, dtype='<i2').astype(np.float64)
        assert np.sqrt(np.mean(samples[50000:70000] ** 2)) < 20, 'Muxed output must retain the silence after cue end'


@pytest.mark.asyncio
async def test_gap_cannot_hide_unfittable_speech(isolated_db, tmp_path, monkeypatch):
    async def tone(text, voice, model, speed, output_path):
        await run_media([settings.get_ffmpeg_bin(), '-y', '-f', 'lavfi', '-i',
                         'sine=frequency=880:sample_rate=24000', '-t', '3', str(output_path)])
    monkeypatch.setattr(tts_service, 'synthesize_speech', tone)
    output = tmp_path / 'rejected.mp3'
    with pytest.raises(RuntimeError, match='Cue 7.*shorten'):
        await tts_service.dub_project_timeline([
            {'cue_index': 7, 'start_time': 1., 'end_time': 2., 'translated_text': 'too long'},
        ], 5., output)
    assert not output.exists()
    assert not output.with_suffix('.timing.json').exists()


@pytest.mark.asyncio
async def test_timing_edit_rejects_past_video_and_invalidates_current_dubbing(isolated_db):
    from app.api.v1.subtitles import update_subtitle_cue
    from app.schemas.subtitle import SubtitleCueUpdate
    project = Project(title='timing', video_duration_seconds=3., dubbed_audio_path='old.mp3', dubbed_audio_url='/old.mp3')
    isolated_db.add(project)
    await isolated_db.flush()
    item = SubtitleCue(project_id=project.id, cue_index=1, start_time=.1, end_time=1., original_text='Hi', translated_text='Hello')
    isolated_db.add(item)
    await isolated_db.commit()
    with pytest.raises(HTTPException) as error:
        await update_subtitle_cue(project.id, item.id, SubtitleCueUpdate(end_time=4.), isolated_db)
    assert error.value.status_code == 422
    await update_subtitle_cue(project.id, item.id, SubtitleCueUpdate(start_time=.2, end_time=.9), isolated_db)
    await isolated_db.refresh(project)
    assert project.dubbed_audio_url is None
    assert (item.start_time, item.end_time) == (.2, .9)


@pytest.mark.asyncio
async def test_timing_report_only_uses_current_owned_project_artifact(isolated_db):
    from app.api.v1.tts import get_project_timing_report
    from app.security import current_user
    project = Project(title='timing report', user_id='local')
    isolated_db.add(project)
    await isolated_db.commit()
    audio = storage_service.get_project_dir(project.id) / 'dubbed_current.mp3'
    audio.write_bytes(b'fixture')
    data = {'version': 1, 'cue_count': 0, 'overlap_cue_count': 0, 'max_speedup': 1., 'cues': []}
    audio.with_suffix('.timing.json').write_text(json.dumps(data), encoding='utf-8')
    project.dubbed_audio_path = str(audio)
    await isolated_db.commit()
    report = await get_project_timing_report(project.id, isolated_db)
    assert report.cue_count == 0
    token = current_user.set('other-user')
    try:
        with pytest.raises(HTTPException) as error:
            await get_project_timing_report(project.id, isolated_db)
        assert error.value.status_code == 404
    finally:
        current_user.reset(token)
    project.dubbed_audio_path = None
    await isolated_db.commit()
    with pytest.raises(HTTPException) as error:
        await get_project_timing_report(project.id, isolated_db)
    assert error.value.status_code == 404


@pytest.mark.asyncio
@pytest.mark.parametrize('case', ['missing', 'corrupt', 'outside'])
async def test_report_rejects_missing_corrupt_or_foreign_path(isolated_db, tmp_path, case):
    from app.api.v1.tts import get_project_timing_report
    project = Project(title='report failures', user_id='local')
    isolated_db.add(project)
    await isolated_db.commit()
    folder = tmp_path if case == 'outside' else storage_service.get_project_dir(project.id)
    audio = folder / 'dubbed.mp3'
    audio.write_bytes(b'fixture')
    if case == 'corrupt':
        audio.with_suffix('.timing.json').write_text('{broken', encoding='utf-8')
    project.dubbed_audio_path = str(audio)
    await isolated_db.commit()
    with pytest.raises(HTTPException) as error:
        await get_project_timing_report(project.id, isolated_db)
    assert error.value.status_code == (500 if case == 'corrupt' else 404)


@pytest.mark.asyncio
async def test_current_timing_report_survives_retention(isolated_db):
    import os
    from app.services.artifact_service import cleanup_expired_scratch
    project = Project(title='retained report')
    isolated_db.add(project)
    await isolated_db.commit()
    folder = storage_service.get_project_dir(project.id)
    audio = folder / 'dubbed.mp3'
    audio.write_bytes(b'audio')
    report = audio.with_suffix('.timing.json')
    report.write_text('{}', encoding='utf-8')
    obsolete = folder / 'obsolete.timing.json'
    obsolete.write_text('{}', encoding='utf-8')
    for path in (audio, report, obsolete):
        os.utime(path, (1, 1))
    project.dubbed_audio_path = str(audio)
    await isolated_db.commit()
    assert await cleanup_expired_scratch(isolated_db) == 1
    assert report.exists() and audio.exists() and not obsolete.exists()
