"""Audit actual speech-window behavior using tones; this is not a quality score.

Only the synthesis provider is replaced. Timing, resampling, tempo, mixing,
encoding, muxing, ASS generation and subtitle rendering use application code.
No live database, media, network or natural-language provider is used.
"""
import asyncio
import json
import os
from pathlib import Path
import sys
from unittest.mock import patch

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
WORK = ROOT / "tmp" / "dubbing-review"
os.environ.update({
    "DATABASE_URL": "sqlite+aiosqlite:///:memory:",
    "STORAGE_DRIVER": "local", "ENV": "development",
    "OUTPUT_DIR": str(WORK / "outputs"), "UPLOAD_DIR": str(WORK / "uploads"),
    "TEMP_SCRATCH_DIR": str(WORK / "scratch"), "API_ACCESS_TOKEN": "",
    "AUTH_USERS": "{}", "OPENAI_API_KEY": "", "GEMINI_API_KEY": "",
    "ANTHROPIC_API_KEY": "", "HF_TOKEN": "",
    "ENABLE_VISUAL_CONTEXT": "false", "ENABLE_SPEAKER_PROFILER": "false",
})
sys.path.insert(0, str(ROOT / "backend"))

from app.config import settings
from app.services.media_process import probe_media, run_media
from app.services.subtitle_generator import subtitle_generator
from app.services.tts_service import tts_service
from app.services.video_burner import VideoBurner


def cue(index: int, start: float, end: float, length: float, frequency: int) -> dict:
    return {"cue_index": index, "start_time": start, "end_time": end,
            "translated_text": f"TONE:{length}:{frequency}", "speaker_tag": f"SPEAKER_{index:02}"}


async def tone_provider(text: str, voice: str, model: str, speed: float, output_path: Path) -> Path:
    _, length, frequency = text.split(":")
    await run_media([settings.get_ffmpeg_bin(), "-y", "-f", "lavfi", "-i",
                     f"sine=frequency={frequency}:sample_rate=24000", "-t", length, str(output_path)])
    return output_path


def tone_intervals(path: Path, frequency: int) -> list[list[float]]:
    """Find tone-active 25-ms windows with a narrow frequency projection.

    Both selected frequencies have integer cycles per window. This prevents
    another overlapping test tone being mistaken for the requested marker.
    The threshold rejects low-level MP3 ringing; boundary resolution is 25 ms.
    """
    samples = np.fromfile(path, dtype="<i2").astype(np.float64)
    window = 600
    frames = samples[:len(samples) // window * window].reshape(-1, window)
    kernel = np.exp(-2j * np.pi * frequency * np.arange(window) / 24000)
    amplitudes = np.abs(frames @ kernel) * 2 / window
    active = np.flatnonzero(amplitudes > 200)
    if not len(active):
        return []
    groups = np.split(active, np.flatnonzero(np.diff(active) != 1) + 1)
    return [[round(float(group[0]) * .025, 3), round(float(group[-1] + 1) * .025, 3)] for group in groups]


async def run_case(name: str, cues: list[dict], duration: float, *, rejected: bool = False) -> dict:
    folder = WORK / name
    folder.mkdir(parents=True, exist_ok=True)
    audio = folder / "timeline.mp3"
    with patch.object(tts_service, "synthesize_speech", tone_provider):
        try:
            await tts_service.dub_project_timeline(cues, duration, audio)
        except RuntimeError as error:
            if not rejected or "cannot fit its timeline" not in str(error):
                raise
            return {"name": name, "expected_rejection": True, "error": str(error)}
    if rejected:
        raise AssertionError("Expected timeline overflow was accepted")
    pcm = folder / "decoded.pcm"
    await run_media([settings.get_ffmpeg_bin(), "-y", "-i", str(audio),
                     "-ar", "24000", "-ac", "1", "-f", "s16le", str(pcm)])
    observations = []
    for item in cues:
        frequency = int(item["translated_text"].split(":")[-1])
        intervals = tone_intervals(pcm, frequency)
        if not intervals:
            raise AssertionError(f"No audible marker for {name} cue {item['cue_index']}")
        observations.append({"cue": item["cue_index"],
                             "subtitle_window_s": [item["start_time"], item["end_time"]],
                             "tone_intervals_s": intervals,
                             "onset_error_s": round(intervals[0][0] - item["start_time"], 3),
                             "speech_past_subtitle_end_s": round(max(0, intervals[-1][1] - item["end_time"]), 3)})
    (folder / "subtitles.ass").write_text(subtitle_generator.generate_ass(cues), encoding="utf-8")
    return {"name": name, "timeline_duration_s": await probe_media(audio, require_audio=True),
            "cues": observations}


async def render_gap_evidence() -> dict:
    folder = WORK / "gap_after_cue"
    source, output = folder / "source.mp4", folder / "burned.mp4"
    await run_media([settings.get_ffmpeg_bin(), "-y", "-f", "lavfi", "-i",
                     "color=c=black:size=320x240:rate=25", "-t", "6", "-c:v", "libx264", str(source)])
    burner = VideoBurner()
    burner._cached_encoder = "libx264"
    await burner.burn_subtitles_to_video(source, folder / "subtitles.ass", output,
                                         mask_original_sub=False, clean_chinese_mode="none")
    counts = {}
    for time in (1.5, 3.0):
        frame = folder / f"frame-{time}.gray"
        await run_media([settings.get_ffmpeg_bin(), "-y", "-ss", str(time), "-i", str(output),
                         "-frames:v", "1", "-pix_fmt", "gray", "-f", "rawvideo", str(frame)])
        pixels = np.fromfile(frame, dtype=np.uint8)
        if pixels.size != 320 * 240:
            raise AssertionError("Unexpected rendered frame size")
        counts[str(time)] = int(np.count_nonzero(pixels > 80))
    if counts["1.5"] == 0 or counts["3.0"] != 0:
        raise AssertionError(f"Subtitle presence/absence probe was inconclusive: {counts}")
    muxed = folder / "dubbed-and-burned.mp4"
    await tts_service.mix_dubbed_video(output, folder / "timeline.mp3", muxed, mix_original=False)
    muxed_pcm = folder / "muxed-decoded.pcm"
    await run_media([settings.get_ffmpeg_bin(), "-y", "-i", str(muxed), "-vn",
                     "-ar", "24000", "-ac", "1", "-f", "s16le", str(muxed_pcm)])
    return {"caption_bright_pixel_count": counts,
            "muxed_first_tone_intervals_s": tone_intervals(muxed_pcm, 880),
            "muxed_duration_s": await probe_media(muxed, require_video=True, require_audio=True),
            "file": str(muxed.relative_to(ROOT))}


async def main() -> None:
    settings.ensure_directories()
    cases = [
        ("short_speech", [cue(1, .5, 1.5, .4, 880)], 3., False),
        ("gap_after_cue", [cue(1, 1., 2., 3., 880), cue(2, 5., 5.5, .25, 1320)], 6., False),
        ("tempo_fit", [cue(1, .5, 1.5, 1.8, 880), cue(2, 1.58, 2., .2, 1320)], 3., False),
        ("overflow_rejected", [cue(1, .5, 1.5, 3., 880), cue(2, 1.58, 2., .2, 1320)], 3., True),
        ("overlapping_cues", [cue(1, 1., 3., 2., 880), cue(2, 2., 4., 1.5, 1320)], 5., False),
        ("last_cue_tail", [cue(1, .5, 1., 2., 880)], 4., False),
    ]
    results = []
    for name, cues, duration, rejected in cases:
        results.append(await run_case(name, cues, duration, rejected=rejected))
    report = {"provider": "synthetic FFmpeg tones; no real words or models",
              "measurement_resolution_s": .025, "cases": results,
              "actual_render_and_mux": await render_gap_evidence()}
    target = WORK / "timing-results.json"
    target.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
