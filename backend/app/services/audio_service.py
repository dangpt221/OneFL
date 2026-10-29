import os
import shutil
import asyncio
import logging
from pathlib import Path
from typing import List, Dict, Any, Tuple
from app.config import settings
from app.services.media_process import run_media, probe_media

logger = logging.getLogger(__name__)


class AudioService:
    """Handles audio demuxing from video and VAD splitting."""

    @staticmethod
    def is_ffmpeg_available() -> bool:
        return bool(settings.get_ffmpeg_bin())

    async def extract_audio_16k_mono(self, video_path: Path, output_audio_path: Path) -> Path:
        """Extracts 16kHz mono WAV from video for ASR processing."""
        output_audio_path.parent.mkdir(parents=True, exist_ok=True)
        ffmpeg_bin = settings.get_ffmpeg_bin()
        
        if self.is_ffmpeg_available():
            cmd = [
                ffmpeg_bin,
                "-y",
                "-i", str(video_path),
                "-vn",
                "-acodec", "pcm_s16le",
                "-ar", "16000",
                "-ac", "1",
                str(output_audio_path)
            ]
            logger.info(f"Running FFmpeg audio extraction: {' '.join(cmd)}")
            await run_media(cmd)
            await probe_media(output_audio_path, require_audio=True)
        else:
            raise RuntimeError("FFmpeg is required for audio extraction")

        return output_audio_path

    async def split_audio_chunks(
        self,
        audio_path: Path,
        total_duration: float,
        chunk_duration: float = 1200.0
    ) -> List[Tuple[int, float, float, Path]]:
        """Calculates chunk boundaries and generates split audio files."""
        chunks = []
        if total_duration <= 0 or chunk_duration <= 0:
            raise ValueError("Audio duration and chunk duration must be positive")
            
        current_start = 0.0
        idx = 0
        while current_start < total_duration:
            current_end = min(current_start + chunk_duration, total_duration)
            chunk_file = audio_path.parent / f"chunk_{idx}_{int(current_start)}_{int(current_end)}.wav"
            await run_media([settings.get_ffmpeg_bin(), '-y', '-ss', str(current_start), '-i', str(audio_path), '-t', str(current_end - current_start), '-c:a', 'pcm_s16le', str(chunk_file)])
            chunks.append((idx, current_start, current_end, chunk_file))
            current_start = current_end
            idx += 1
            
        return chunks


audio_service = AudioService()
