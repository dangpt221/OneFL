import os
import shutil
import asyncio
import logging
from pathlib import Path
from typing import List, Optional, Dict, Any
from app.config import settings

logger = logging.getLogger(__name__)


class VideoBurner:
    """Handles rendering/burning subtitles onto video and lossless stitching with auto GPU hardware acceleration."""

    _cached_encoder: Optional[str] = None

    @staticmethod
    def is_ffmpeg_available() -> bool:
        return bool(settings.get_ffmpeg_bin())

    async def detect_best_encoder(self) -> str:
        """
        Detects the best available video encoder on the system (Nvidia NVENC -> Intel QSV -> AMD AMF -> CPU libx264).
        (Adapted from PyVideoTrans hardware acceleration detection logic).
        """
        if self._cached_encoder:
            return self._cached_encoder

        ffmpeg_bin = settings.get_ffmpeg_bin()
        if not ffmpeg_bin:
            return "libx264"

        # Candidate encoders in order of performance priority
        candidates = ["h264_nvenc", "h264_qsv", "h264_amf"]
        for enc in candidates:
            cmd = [
                ffmpeg_bin,
                "-y", "-hide_banner",
                "-f", "lavfi",
                "-i", "testsrc=duration=0.2:size=320x240:rate=30",
                "-c:v", enc,
                "-f", "null", "-"
            ]
            try:
                proc = await asyncio.create_subprocess_exec(
                    *cmd,
                    stdout=asyncio.subprocess.DEVNULL,
                    stderr=asyncio.subprocess.DEVNULL
                )
                await asyncio.wait_for(proc.wait(), timeout=3.0)
                if proc.returncode == 0:
                    logger.info(f"Hardware video encoder detected and verified: {enc}")
                    self._cached_encoder = enc
                    return enc
            except Exception as e:
                logger.debug(f"Encoder test {enc} failed or timed out: {e}")

        logger.info("No hardware GPU encoder available. Using software CPU libx264.")
        self._cached_encoder = "libx264"
        return "libx264"

    def _get_encoder_args(self, encoder: str) -> List[str]:
        """Returns optimal encoding parameters for the given codec."""
        if encoder == "h264_nvenc":
            return ["-c:v", "h264_nvenc", "-preset", settings.NVENC_PRESET, "-cq", str(settings.NVENC_CQ_LEVEL)]
        elif encoder == "h264_qsv":
            return ["-c:v", "h264_qsv", "-global_quality", "23"]
        elif encoder == "h264_amf":
            return ["-c:v", "h264_amf", "-quality", "speed"]
        else:
            return ["-c:v", "libx264", "-preset", "veryfast", "-crf", "22"]

    async def burn_subtitles_to_video(
        self,
        video_path: Path,
        ass_subtitle_path: Path,
        output_video_path: Path,
        mask_original_sub: bool = True,
        gpu_device_id: int = 0
    ) -> Path:
        """Burns ASS subtitles into video using auto-detected GPU hardware acceleration or libx264."""
        output_video_path.parent.mkdir(parents=True, exist_ok=True)
        ffmpeg_bin = settings.get_ffmpeg_bin()
        
        if self.is_ffmpeg_available():
            # Use relative filename with cwd to prevent Windows colon/drive letter parsing errors in FFmpeg filtergraph
            ass_filename = ass_subtitle_path.name
            ass_dir = ass_subtitle_path.parent

            # Filter: Optional solid black banner to completely conceal original hardcoded foreign subtitles (100% opaque)
            if mask_original_sub:
                vf_filter = f"drawbox=x=0:y=ih-102:w=iw:h=88:color=black@1.0:t=fill,ass={ass_filename}"
            else:
                vf_filter = f"ass={ass_filename}"

            best_enc = await self.detect_best_encoder()
            enc_args = self._get_encoder_args(best_enc)

            cmd = [
                ffmpeg_bin,
                "-y",
                "-i", str(video_path.resolve()),
                "-vf", vf_filter,
                *enc_args,
                "-c:a", "aac",
                "-b:a", settings.BURN_OUTPUT_AUDIO_BITRATE,
                str(output_video_path.resolve())
            ]
            logger.info(f"Burning subtitles with {best_enc} in {ass_dir}: {' '.join(cmd)}")
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                cwd=str(ass_dir),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await proc.communicate()
            if proc.returncode != 0:
                logger.warning(f"Hardware burn with {best_enc} failed ({stderr.decode(errors='ignore')}). Retrying with libx264 CPU fallback...")
                cpu_args = self._get_encoder_args("libx264")
                cpu_cmd = [
                    ffmpeg_bin,
                    "-y",
                    "-i", str(video_path.resolve()),
                    "-vf", vf_filter,
                    *cpu_args,
                    "-c:a", "aac",
                    "-b:a", settings.BURN_OUTPUT_AUDIO_BITRATE,
                    str(output_video_path.resolve())
                ]
                proc_cpu = await asyncio.create_subprocess_exec(
                    *cpu_cmd,
                    cwd=str(ass_dir),
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )
                await proc_cpu.communicate()
                if proc_cpu.returncode != 0:
                    logger.warning("FFmpeg burn failed completely. Copying original video.")
                    shutil.copyfile(video_path, output_video_path)
        else:
            logger.info("FFmpeg not available. Copying video file as burned output simulation.")
            if video_path.exists():
                shutil.copyfile(video_path, output_video_path)
            else:
                # Create small placeholder video
                with open(output_video_path, "wb") as f:
                    f.write(b"placeholder_video_data")

        return output_video_path

    async def lossless_concat_chunks(
        self,
        chunk_video_paths: List[Path],
        output_final_path: Path
    ) -> Path:
        """Losslessly concatenates burned video chunks using FFmpeg Concat Demuxer."""
        output_final_path.parent.mkdir(parents=True, exist_ok=True)
        
        if not chunk_video_paths:
            return output_final_path

        if len(chunk_video_paths) == 1:
            if chunk_video_paths[0].exists():
                shutil.copyfile(chunk_video_paths[0], output_final_path)
            return output_final_path

        filelist_txt = output_final_path.parent / "filelist.txt"
        with open(filelist_txt, "w", encoding="utf-8") as f:
            for p in chunk_video_paths:
                f.write(f"file '{p.resolve().as_posix()}'\n")

        if self.is_ffmpeg_available():
            cmd = [
                settings.FFMPEG_PATH,
                "-y",
                "-f", "concat",
                "-safe", "0",
                "-i", str(filelist_txt),
                "-c", "copy",
                str(output_final_path)
            ]
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            await proc.communicate()
        else:
            if chunk_video_paths[0].exists():
                shutil.copyfile(chunk_video_paths[0], output_final_path)

        return output_final_path


video_burner = VideoBurner()
