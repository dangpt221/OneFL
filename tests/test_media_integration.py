"""Real FFmpeg smoke tests on seconds of generated media, never user videos."""
from pathlib import Path
import pytest
from app.config import settings
from app.models.project import Project
from app.models.subtitle import SubtitleCue
from tests.test_reliability import isolated_db


@pytest.mark.asyncio
async def test_actual_multichunk_burn_preserves_silent_tail(isolated_db, tmp_path, monkeypatch):
    from app.services.media_process import run_media, probe_media
    from app.services.workflow_engine import workflow_engine
    from app.services.video_burner import video_burner
    source = tmp_path / 'source.mp4'
    await run_media([settings.get_ffmpeg_bin(), '-y', '-f', 'lavfi', '-i', 'testsrc=size=320x240:rate=15',
                     '-f', 'lavfi', '-i', 'sine=frequency=440:sample_rate=24000', '-t', '3',
                     '-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-g', '45', '-c:a', 'aac', str(source)])
    project = Project(title='real short media', local_video_path=str(source), video_duration_seconds=0.7,
                      settings_override={'clean_chinese_mode': 'none', 'mask_original_sub': False})
    isolated_db.add(project)
    await isolated_db.flush()
    isolated_db.add(SubtitleCue(project_id=project.id, cue_index=1, start_time=.1, end_time=.7, original_text='Hello', translated_text='Xin chào'))
    await isolated_db.commit()
    monkeypatch.setattr(settings, 'VIDEO_CHUNK_DURATION_SECONDS', 1)
    monkeypatch.setattr(video_burner, '_cached_encoder', 'libx264')
    await workflow_engine.burn_project_video(isolated_db, project.id)
    assert project.status == 'COMPLETED'
    assert abs(project.video_duration_seconds - 3.) < .1
    assert abs(await probe_media(Path(project.burned_video_path), require_video=True, require_audio=True) - 3.) < .2


@pytest.mark.asyncio
async def test_actual_dubbing_timeline_and_mux(isolated_db, tmp_path, monkeypatch):
    from app.services.media_process import run_media, probe_media
    from app.services.tts_service import tts_service
    async def local_speech(text, voice, model, speed, output_path):
        await run_media([settings.get_ffmpeg_bin(), '-y', '-f', 'lavfi', '-i', 'sine=frequency=880:sample_rate=24000', '-t', '0.4', str(output_path)])
        return output_path
    monkeypatch.setattr(tts_service, 'synthesize_speech', local_speech)
    output = tmp_path / 'timeline.mp3'
    await tts_service.dub_project_timeline([
        {'cue_index': 1, 'start_time': .2, 'end_time': 1., 'translated_text': 'Xin chào'},
        {'cue_index': 2, 'start_time': 1.5, 'end_time': 2., 'translated_text': 'Tạm biệt'},
    ], 3., output)
    assert abs(await probe_media(output, require_audio=True) - 3.) < .2
    source, muxed = tmp_path / 'source.mp4', tmp_path / 'dubbed.mp4'
    await run_media([settings.get_ffmpeg_bin(), '-y', '-f', 'lavfi', '-i', 'color=c=blue:size=320x240:rate=15',
                     '-f', 'lavfi', '-i', 'sine=frequency=440:sample_rate=24000', '-t', '3',
                     '-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-c:a', 'aac', str(source)])
    await tts_service.mix_dubbed_video(source, output, muxed, mix_original=True, ducking_volume=.1)
    assert abs(await probe_media(muxed, require_video=True, require_audio=True) - 3.) < .2


@pytest.mark.asyncio
@pytest.mark.parametrize('mode,top,bottom', [('cinema_bars', 0, .15), ('bottom_bar', .11, 0), ('smart_blur', 0, .15), ('smart_blur', .11, .15), ('cinema_zoom', .11, .15)])
async def test_actual_filter_modes_handle_zero_and_nonzero_masks(isolated_db, tmp_path, monkeypatch, mode, top, bottom):
    from app.services.media_process import run_media, probe_media
    from app.services.video_burner import VideoBurner
    from app.services.subtitle_generator import subtitle_generator
    source, subtitle, output = tmp_path / 'source.mp4', tmp_path / 'sample.ass', tmp_path / 'burn.mp4'
    await run_media([settings.get_ffmpeg_bin(), '-y', '-f', 'lavfi', '-i', 'color=c=blue:size=320x240:rate=15', '-t', '0.5', '-c:v', 'libx264', str(source)])
    subtitle.write_text(subtitle_generator.generate_ass([{'start_time': 0, 'end_time': .4, 'translated_text': 'Test'}]), encoding='utf-8')
    burner = VideoBurner()
    burner._cached_encoder = 'libx264'
    await burner.burn_subtitles_to_video(source, subtitle, output, True, mode, top, bottom)
    assert await probe_media(output, require_video=True) > 0
