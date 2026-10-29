"""Actual pixel restoration, streaming media and cleanup admission regressions."""
from pathlib import Path
import asyncio
import numpy as np
import pytest
from pydantic import ValidationError


@pytest.mark.parametrize('region', [
    {'x': -.1, 'y': 0, 'width': .1, 'height': .1},
    {'x': .9, 'y': .1, 'width': .2, 'height': .1},
    {'x': .1, 'y': .9, 'width': .1, 'height': .2},
    {'x': 0, 'y': 0, 'width': 0, 'height': .1},
    {'x': float('nan'), 'y': 0, 'width': .1, 'height': .1},
    {'x': 0, 'y': 0, 'width': 1, 'height': .9},
    {'x': 0, 'y': 0, 'width': .1, 'height': .1, 'reference_time': -1},
])
def test_region_rejects_outside_empty_nonfinite_or_huge_masks(region):
    from app.schemas.video_cleanup import CleanupRegion
    with pytest.raises(ValidationError):
        CleanupRegion(**region)


def test_burn_accepts_typed_cleanup_and_bounds_region_count():
    from app.schemas.translation import BurnOptionsRequest
    from app.schemas.video_cleanup import VideoCleanupOptions
    config = BurnOptionsRequest(clean_chinese_mode='inpaint', cleanup_options={
        'auto_detect_chinese': False, 'regions': [{'x': .1, 'y': .1, 'width': .1, 'height': .1, 'track': True}]})
    assert config.cleanup_options.regions[0].track
    with pytest.raises(ValidationError):
        VideoCleanupOptions(regions=[{'x': 0, 'y': 0, 'width': .1, 'height': .1}] * 13)
    with pytest.raises(ValidationError):
        VideoCleanupOptions(scan_interval_seconds=float('inf'))


def processor(config, **kwargs):
    pytest.importorskip('cv2', reason='Install backend[cleanup] for pixel cleanup tests')
    from app.schemas.video_cleanup import VideoCleanupOptions
    from app.services.video_cleanup import CleanupProcessor
    return CleanupProcessor(VideoCleanupOptions(**config), **kwargs)


def test_real_inpaint_removes_pixels_and_preserves_unmasked_background():
    original = np.full((120, 200, 3), (70, 100, 130), dtype=np.uint8)
    dirty = original.copy(); dirty[30:50, 40:80] = (255, 255, 255)
    p = processor({'auto_detect_chinese': False, 'padding': 2,
                   'regions': [{'x': .2, 'y': .25, 'width': .2, 'height': 1/6}]})
    clean = p.process(dirty, 0.)
    assert abs(clean[35:45, 45:75].astype(float) - original[35:45, 45:75]).mean() < 8
    assert np.array_equal(clean[:20], original[:20])
    assert p.stats['masked_frames'] == 1


def test_ocr_targets_chinese_and_does_not_reuse_stale_boxes():
    from app.services.cleanup_ocr import TextDetection
    frame = np.full((120, 200, 3), 90, dtype=np.uint8); frame[30:50, 40:80] = 255
    detections = [TextDetection([[40,30],[80,30],[80,50],[40,50]], '中文字幕', .95),
                  TextDetection([[110,30],[150,30],[150,50],[110,50]], 'English', .95)]
    calls = []
    def detect(image):
        calls.append(1); return detections if len(calls) == 1 else []
    p = processor({'auto_detect_chinese': True, 'scan_interval_seconds': .5, 'padding': 2}, detector=detect)
    clean = p.process(frame, 0.)
    assert clean[35:45,45:75].mean() < 110
    assert np.array_equal(clean[30:50,110:150], frame[30:50,110:150])
    assert np.array_equal(p.process(frame, .6), frame)
    assert p.stats['ocr_scans'] == 2 and p.stats['chinese_detections'] == 1


def test_template_tracking_follows_moving_logo():
    rng = np.random.default_rng(4)
    logo = rng.integers(130, 255, (16, 24, 3), dtype=np.uint8)
    first = np.full((120,200,3), 80, dtype=np.uint8); first[24:40,30:54] = logo
    moved = np.full_like(first,80); moved[30:46,90:114] = logo
    p = processor({'auto_detect_chinese': False, 'padding': 1,
                   'regions': [{'x': .15, 'y': .2, 'width': .12, 'height': 16/120, 'track': True}]},
                  reference_loader=lambda _: first)
    clean = p.process(moved, 1.)
    assert clean[32:44,92:112].mean() < 100
    assert p.stats['tracking_misses'] == 0
    assert np.array_equal(clean[:20], moved[:20])


def test_missing_logo_is_reported_and_not_erased_elsewhere():
    rng = np.random.default_rng(5)
    first = np.full((100,160,3), 80, dtype=np.uint8); first[20:40,20:44] = rng.integers(130,255,(20,24,3),dtype=np.uint8)
    blank = np.full_like(first,80)
    p = processor({'auto_detect_chinese': False,
                   'regions': [{'x': .125,'y': .2,'width': .15,'height': .2,'track':True}]},
                  reference_loader=lambda _: first)
    assert np.array_equal(p.process(blank, 2.), blank)
    assert p.stats['tracking_misses'] == 1


def test_mask_area_guard_and_missing_ocr_are_explicit():
    from app.services.cleanup_ocr import TextDetection
    p = processor({'auto_detect_chinese': True}, detector=lambda _: [TextDetection([[0,0],[199,0],[199,119],[0,119]], '中文', .99)])
    with pytest.raises(RuntimeError, match='50%'):
        p.process(np.zeros((120,200,3),dtype=np.uint8), 0.)


@pytest.mark.asyncio
async def test_streaming_cleanup_keeps_audio_timing_and_burns_translation_last(tmp_path):
    pytest.importorskip('cv2')
    from app.config import settings
    from app.services.media_process import run_media, probe_media
    from app.services.subtitle_generator import subtitle_generator
    from app.services.video_cleanup import burn_cleaned_video
    from app.schemas.video_cleanup import VideoCleanupOptions
    source, subtitle, output = tmp_path/'source.mp4',tmp_path/'sample.ass',tmp_path/'clean.mp4'
    await run_media([settings.get_ffmpeg_bin(),'-y','-f','lavfi','-i',
        'color=c=0x466482:size=320x240:rate=15,drawbox=x=40:y=40:w=60:h=24:color=white:t=fill',
        '-f','lavfi','-i','sine=frequency=440:sample_rate=24000','-t','3','-c:v','libx264','-pix_fmt','yuv420p','-c:a','aac',str(source)])
    subtitle.write_text(subtitle_generator.generate_ass([{'start_time':0,'end_time':1.8,'translated_text':'Xin chao'}]),encoding='utf-8')
    options=VideoCleanupOptions(auto_detect_chinese=False,padding=3,regions=[{'x':40/320,'y':40/240,'width':60/320,'height':24/240}])
    result=await burn_cleaned_video(source,subtitle,output,options,['-c:v','libx264','-preset','ultrafast','-crf','18'],start_time=1.,duration=2.)
    assert abs(await probe_media(output,require_video=True,require_audio=True)-2.)<.15
    assert result['processed_frames']==30 and result['masked_frames']==30
    rgb,_=await run_media([settings.get_ffmpeg_bin(),'-v','error','-ss','0.5','-i',str(output),'-frames:v','1','-pix_fmt','rgb24','-f','rawvideo','-'])
    frame=np.frombuffer(rgb,dtype=np.uint8).reshape(240,320,3)
    assert frame[44:58,45:95].mean()<180  # Original white mark is removed.
    assert frame[185:235].max()>210  # New translated ASS survives the removal pass.
    assert output.with_suffix('.cleanup.json').is_file()


@pytest.mark.asyncio
async def test_cancel_cleanup_waits_for_worker_and_removes_partial(tmp_path,monkeypatch):
    pytest.importorskip('cv2')
    import threading
    from app.schemas.video_cleanup import VideoCleanupOptions
    from app.services import video_cleanup as module
    entered,exited=threading.Event(),threading.Event()
    output=tmp_path/'partial.mp4'
    def blocked(*args,**kwargs):
        group=kwargs['group'];output.write_bytes(b'partial');entered.set()
        try:
            group.cancelled.wait(2)
        finally:
            exited.set()
        raise RuntimeError('cancelled worker')
    monkeypatch.setattr(module,'_stream_cleanup',blocked)
    options=VideoCleanupOptions(auto_detect_chinese=False,regions=[{'x':.1,'y':.1,'width':.1,'height':.1}])
    task=asyncio.create_task(module.burn_cleaned_video(Path('source'),Path('sub'),output,options,[]))
    for _ in range(100):
        if entered.is_set():break
        await asyncio.sleep(.01)
    assert entered.is_set();task.cancel()
    with pytest.raises(asyncio.CancelledError):await asyncio.wait_for(task,3)
    assert exited.is_set() and not output.exists()


@pytest.mark.asyncio
async def test_cleanup_hardware_encoder_failure_falls_back_without_losing_options(tmp_path, monkeypatch):
    import app.services.video_cleanup as cleanup
    from app.services.video_burner import VideoBurner
    calls = []
    async def encode(source, subtitle, output, options, encoder_args, **kwargs):
        calls.append((encoder_args, options.model_dump(), kwargs))
        if encoder_args[1] != 'libx264':
            raise cleanup.CleanupEncodingError('fixture unavailable GPU encoder')
        output.write_bytes(b'fixture valid result')
    monkeypatch.setattr(cleanup, 'burn_cleaned_video', encode)
    burner = VideoBurner()
    burner._cached_encoder = 'h264_nvenc'
    options = {'auto_detect_chinese': False, 'regions': [{'x': .1, 'y': .1, 'width': .1, 'height': .1}]}
    await burner.burn_subtitles_to_video(tmp_path/'source', tmp_path/'sub.ass', tmp_path/'out.mp4',
        clean_chinese_mode='inpaint', cleanup_options=options, start_time=2, duration=3)
    assert [call[0][1] for call in calls] == ['h264_nvenc', 'libx264']
    assert calls[0][1:] == calls[1][1:]


@pytest.mark.asyncio
@pytest.mark.parametrize('hdr', [False, True])
async def test_cleanup_preserves_pixel_aspect_and_rejects_hdr(tmp_path, hdr):
    pytest.importorskip('cv2')
    import av
    from app.config import settings
    from app.services.media_process import run_media
    from app.services.subtitle_generator import subtitle_generator
    from app.services.video_cleanup import burn_cleaned_video
    from app.schemas.video_cleanup import VideoCleanupOptions
    source, subtitle, output = tmp_path/'source.mp4', tmp_path/'sub.ass', tmp_path/'clean.mp4'
    await run_media([settings.get_ffmpeg_bin(), '-y', '-f', 'lavfi', '-i',
        'color=c=blue:size=320x240:rate=15,setsar=2/1', '-t', '0.5', '-c:v', 'libx264',
        *(['-x264-params', 'colorprim=bt2020:transfer=smpte2084:colormatrix=bt2020nc'] if hdr else []), str(source)])
    subtitle.write_text(subtitle_generator.generate_ass([]), encoding='utf8')
    options = VideoCleanupOptions(auto_detect_chinese=False, regions=[{'x': .1, 'y': .1, 'width': .1, 'height': .1}])
    if hdr:
        with pytest.raises(RuntimeError, match='SDR'):
            await burn_cleaned_video(source, subtitle, output, options, ['-c:v', 'libx264'])
        assert not output.exists()
    else:
        await burn_cleaned_video(source, subtitle, output, options, ['-c:v', 'libx264'])
        with av.open(str(output)) as media:
            assert float(media.streams.video[0].sample_aspect_ratio) == 2
