import pytest
from pathlib import Path
from app.services.video_burner import video_burner
from app.config import settings


def test_build_video_filter_cinema_bars():
    vf = video_burner.build_video_filter(
        ass_filename="subtitles.ass",
        clean_chinese_mode="cinema_bars",
        mask_original_sub=True,
        top_mask_pct=0.11,
        bottom_mask_pct=0.15
    )
    assert "drawbox=" in vf
    assert "color=black@1.0" in vf
    assert "ass=subtitles.ass" in vf


def test_build_video_filter_none():
    vf = video_burner.build_video_filter(
        ass_filename="subtitles.ass",
        clean_chinese_mode="none",
        mask_original_sub=False
    )
    assert vf == "ass=subtitles.ass"


def test_build_video_filter_smart_blur():
    vf = video_burner.build_video_filter(
        ass_filename="subtitles.ass",
        clean_chinese_mode="smart_blur",
        mask_original_sub=True
    )
    assert "boxblur=" in vf
    assert "ass=subtitles.ass" in vf


@pytest.mark.asyncio
async def test_detect_best_encoder():
    encoder = await video_burner.detect_best_encoder()
    assert encoder in ["h264_nvenc", "h264_qsv", "h264_amf", "libx264"]


@pytest.mark.asyncio
async def test_lossless_concat_chunks_empty(tmp_path):
    output_path = tmp_path / "out_concat.mp4"
    result = await video_burner.lossless_concat_chunks([], output_path)
    assert result == output_path
