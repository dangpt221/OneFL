"""Reference comic subtitles and opaque white bands on real short media."""
from pathlib import Path

import numpy as np
import pytest

from app.config import settings
from app.models.project import Project
from app.models.subtitle import SubtitleCue
from app.schemas.translation import BurnOptionsRequest
from app.services.subtitle_generator import subtitle_generator
from app.services.video_burner import VideoBurner
from tests.test_reliability import isolated_db


def test_burn_default_and_explicit_legacy_styles():
    defaults = BurnOptionsRequest()
    assert (defaults.subtitle_preset, defaults.clean_chinese_mode) == ('comic', 'white_bars')
    legacy = BurnOptionsRequest(subtitle_preset='box_banner', clean_chinese_mode='cinema_bars')
    assert (legacy.subtitle_preset, legacy.clean_chinese_mode) == ('box_banner', 'cinema_bars')
    assert BurnOptionsRequest(subtitle_preset='comic', clean_chinese_mode='white_bars').mask_original_sub


def test_comic_ass_caps_preserve_vietnamese_and_original_text():
    cues = [{'start_time': 0, 'end_time': 1, 'original_text': '原文',
             'translated_text': 'Ta đã hỏi ở Túy Tiên Lầu rồi.\nMời hai bàn tiệc.'}]
    result = subtitle_generator.generate_ass(cues, preset='comic')
    fields = next(line for line in result.splitlines() if line.startswith('Style: Default,')).split(',')
    assert fields[1:4] == ['Arial', '36', '&H00FFFFFF']
    assert fields[7:9] == ['1', '1']  # Bold and italic.
    assert fields[11:13] == ['80', '100']
    assert fields[15:18] == ['1', '3', '1']  # Outline/shadow, no rectangle.
    assert 'TA ĐÃ HỎI Ở TÚY TIÊN LẦU RỒI.\\NMỜI HAI BÀN TIỆC.' in result
    assert cues[0]['translated_text'].startswith('Ta đã hỏi')
    assert 'Ta đã hỏi' in subtitle_generator.generate_srt(cues)
    assert 'Ta đã hỏi' in subtitle_generator.generate_ass(cues, preset='cinema')
    bilingual = subtitle_generator.generate_ass(cues, preset='comic', bilingual=True)
    assert '原文' in bilingual and 'TA ĐÃ HỎI' in bilingual


@pytest.mark.parametrize('top,bottom,count', [(0, 0, 0), (0, .15, 1), (.11, 0, 1), (.11, .15, 2)])
def test_white_filter_skips_zero_heights_and_burns_translation_last(top, bottom, count):
    result = VideoBurner().build_video_filter('sample.ass', 'white_bars', True, top, bottom)
    assert result.count('color=white@1.0') == count
    assert 'black' not in result
    assert result.endswith('ass=sample.ass')
    assert VideoBurner().build_video_filter('sample.ass', 'white_bars', False, top, bottom) == 'ass=sample.ass'


@pytest.mark.asyncio
async def test_real_white_bands_keep_center_audio_timeline_and_visible_comic_text(tmp_path):
    import av
    from app.services.media_process import run_media, probe_media
    source, subtitle, output = tmp_path/'source.mp4', tmp_path/'sample.ass', tmp_path/'white.mp4'
    await run_media([settings.get_ffmpeg_bin(), '-y', '-f', 'lavfi', '-i',
        'color=c=blue:size=640x360:rate=15,drawbox=x=10:y=4:w=200:h=25:color=black:t=fill,drawbox=x=10:y=320:w=200:h=25:color=black:t=fill',
        '-f', 'lavfi', '-i', 'sine=frequency=440:sample_rate=24000', '-t', '1.5',
        '-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-c:a', 'aac', str(source)])
    subtitle.write_text(subtitle_generator.generate_ass([
        {'start_time': 0, 'end_time': .8, 'translated_text': 'Ta đã hỏi rồi. Mời hai bàn tiệc.'}], preset='comic'), encoding='utf-8')
    burner = VideoBurner()
    burner._cached_encoder = 'libx264'
    await burner.burn_subtitles_to_video(source, subtitle, output, clean_chinese_mode='white_bars')
    assert abs(await probe_media(output, require_video=True, require_audio=True) - 1.5) < .2
    with av.open(str(output)) as media:
        assert (media.streams.video[0].width, media.streams.video[0].height) == (640, 360)
    async def frame_at(timestamp):
        rgb, _ = await run_media([settings.get_ffmpeg_bin(), '-v', 'error', '-ss', timestamp,
            '-i', str(output), '-frames:v', '1', '-pix_fmt', 'rgb24', '-f', 'rawvideo', '-'])
        return np.frombuffer(rgb, dtype=np.uint8).reshape(360, 640, 3)
    active, blank = await frame_at('0.3'), await frame_at('1.2')
    assert blank[2:35, 2:630].min() >= 245  # Opaque white replaces source mark.
    assert blank[312:358, 2:630].min() >= 245
    assert active[150:250, 20:620, 2].mean() > 240  # Center remains original blue.
    assert active[150:250, 20:620, :2].max() < 15
    assert (active[305:358].max(axis=2) < 80).sum() > 100  # Black outlines survive white band.
    assert np.abs(active[305:358].astype(float) - blank[305:358]).sum() > 30000


@pytest.mark.asyncio
@pytest.mark.parametrize('top,bottom', [(0, .15), (.11, 0), (.00001, .00001)])
async def test_real_white_bands_do_not_fill_whole_frame_for_zero_or_tiny_sizes(tmp_path, top, bottom):
    from app.services.media_process import run_media
    source, subtitle, output = tmp_path/'source.mp4', tmp_path/'empty.ass', tmp_path/'white.mp4'
    await run_media([settings.get_ffmpeg_bin(), '-y', '-f', 'lavfi', '-i',
        'color=c=blue:size=320x240:rate=15', '-t', '0.4', '-c:v', 'libx264', str(source)])
    subtitle.write_text(subtitle_generator.generate_ass([], preset='comic'), encoding='utf-8')
    burner = VideoBurner()
    burner._cached_encoder = 'libx264'
    await burner.burn_subtitles_to_video(source, subtitle, output,
        clean_chinese_mode='white_bars', top_mask_pct=top, bottom_mask_pct=bottom)
    rgb, _ = await run_media([settings.get_ffmpeg_bin(), '-v', 'error', '-i', str(output),
        '-frames:v', '1', '-pix_fmt', 'rgb24', '-f', 'rawvideo', '-'])
    frame = np.frombuffer(rgb, dtype=np.uint8).reshape(240, 320, 3)
    assert frame[80:160, :, 2].mean() > 240 and frame[80:160, :, :2].max() < 15
    if top == 0:
        assert frame[4:15, :, :2].max() < 15
    if bottom == 0:
        assert frame[225:235, :, :2].max() < 15


@pytest.mark.asyncio
@pytest.mark.parametrize('saved', [{}, {'subtitle_preset': 'cinema', 'clean_chinese_mode': 'none'}])
async def test_workflow_uses_new_defaults_and_preserves_saved_choices(isolated_db, tmp_path, monkeypatch, saved):
    from app.services.media_process import run_media
    from app.services.workflow_engine import workflow_engine
    from app.services.video_burner import video_burner
    source = tmp_path/'source.mp4'
    await run_media([settings.get_ffmpeg_bin(), '-y', '-f', 'lavfi', '-i',
        'color=c=blue:size=320x240:rate=15', '-t', '0.5', '-c:v', 'libx264', str(source)])
    project = Project(title='white band defaults', local_video_path=str(source), settings_override=saved.copy())
    isolated_db.add(project)
    await isolated_db.flush()
    isolated_db.add(SubtitleCue(project_id=project.id, cue_index=1, start_time=0, end_time=.4,
                               original_text='Hello', translated_text='Xin chào'))
    await isolated_db.commit()
    calls = []
    original = video_burner.burn_subtitles_to_video
    async def record(video, ass, output, **kwargs):
        calls.append((ass.read_text(encoding='utf-8'), kwargs['clean_chinese_mode']))
        return await original(video, ass, output, **kwargs)
    monkeypatch.setattr(video_burner, 'burn_subtitles_to_video', record)
    monkeypatch.setattr(video_burner, '_cached_encoder', 'libx264')
    await workflow_engine.burn_project_video(isolated_db, project.id)
    assert project.status == 'COMPLETED'
    assert calls[0][1] == saved.get('clean_chinese_mode', 'white_bars')
    assert ('XIN CHÀO' in calls[0][0]) == (not saved)
    assert project.settings_override == saved  # Rendering never mutates persisted choices.
