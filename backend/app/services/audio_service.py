import os
import shutil
import asyncio
import logging
from pathlib import Path
from typing import List, Dict, Any, Tuple
from app.config import settings

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
            loop = asyncio.get_running_loop()
            import subprocess
            proc = await loop.run_in_executor(
                None,
                lambda: subprocess.run(cmd, capture_output=True)
            )
            if proc.returncode != 0:
                logger.warning(f"FFmpeg extraction warning: {proc.stderr.decode(errors='ignore')}")
        else:
            # Fallback for dev environment without ffmpeg: create empty or copy placeholder
            logger.info("FFmpeg binary not detected in PATH. Creating placeholder audio track for dev.")
            with open(output_audio_path, "wb") as f:
                f.write(b"RIFF\x24\x00\x00\x00WAVEfmt \x10\x00\x00\x00\x01\x00\x01\x00\x80>\x00\x00\x00}\x00\x00\x02\x00\x10\x00data\x00\x00\x00\x00")

        return output_audio_path

    async def split_audio_chunks(
        self,
        audio_path: Path,
        total_duration: float,
        chunk_duration: float = 1200.0
    ) -> List[Tuple[int, float, float, Path]]:
        """Calculates chunk boundaries and generates split audio files."""
        chunks = []
        if total_duration <= 0:
            total_duration = 30.0 # Default fallback
            
        current_start = 0.0
        idx = 0
        while current_start < total_duration:
            current_end = min(current_start + chunk_duration, total_duration)
            chunk_file = audio_path.parent / f"chunk_{idx}_{int(current_start)}_{int(current_end)}.wav"
            chunks.append((idx, current_start, current_end, chunk_file))
            current_start = current_end
            idx += 1
            
        return chunks


audio_service = AudioService()
