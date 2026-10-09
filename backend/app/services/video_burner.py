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

    def build_video_filter(
        self,
        ass_filename: str,
        clean_chinese_mode: str = "cinema_bars",
        mask_original_sub: bool = True,
        top_mask_pct: float = 0.11,
        bottom_mask_pct: float = 0.15
    ) -> str:
        """
        Builds the FFmpeg video filter for removing Chinese text, watermarks, and rendering ASS subtitles.
        Modes:
        - 'cinema_bars': Top black bar (covers Bilibili logo & top watermark) + Bottom black bar (covers Chinese hardsub).
        - 'bottom_bar': Bottom black bar only (covers Chinese hardsub).
        - 'smart_blur': Boxblur on top logo area and bottom subtitle area.
        - 'cinema_zoom': Crop top & bottom and scale to full frame (zoom 108-112%), eliminating borders.
        - 'none': Direct subtitle burn without masking.
        """
        top_pct = max(0.04, min(0.28, float(top_mask_pct)))
        bot_pct = max(0.06, min(0.35, float(bottom_mask_pct)))

        if not mask_original_sub or clean_chinese_mode == "none":
            return f"ass={ass_filename}"

        if clean_chinese_mode == "cinema_bars":
            return (
                f"drawbox=x=0:y=0:w=iw:h=ih*{top_pct:.3f}:color=black@1.0:t=fill,"
                f"drawbox=x=0:y=ih-ih*{bot_pct:.3f}:w=iw:h=ih*{bot_pct:.3f}:color=black@1.0:t=fill,"
                f"ass={ass_filename}"
            )
        elif clean_chinese_mode == "bottom_bar":
            return (
                f"drawbox=x=0:y=ih-ih*{bot_pct:.3f}:w=iw:h=ih*{bot_pct:.3f}:color=black@1.0:t=fill,"
                f"ass={ass_filename}"
            )
        elif clean_chinese_mode == "smart_blur":
            return (
                f"split[m0][b0];"
                f"[b0]crop=iw:ih*{top_pct:.3f}:0:0,boxblur=8:2[topb];"
                f"[m0][topb]overlay=0:0[m1];"
                f"[m1]split[m2][b1];"
                f"[b1]crop=iw:ih*{bot_pct:.3f}:0:ih-ih*{bot_pct:.3f},boxblur=8:2[botb];"
                f"[m2][botb]overlay=0:H-h[m3];"
                f"[m3]ass={ass_filename}"
            )
        elif clean_chinese_mode == "cinema_zoom":
            cut_pct = top_pct + bot_pct
            return (
                f"crop=iw:ih*(1.0-{cut_pct:.3f}):0:ih*{top_pct:.3f},"
                f"scale=iw:ih:flags=lanczos,"
                f"ass={ass_filename}"
            )
        else:
            return (
                f"drawbox=x=0:y=0:w=iw:h=ih*{top_pct:.3f}:color=black@1.0:t=fill,"
                f"drawbox=x=0:y=ih-ih*{bot_pct:.3f}:w=iw:h=ih*{bot_pct:.3f}:color=black@1.0:t=fill,"
                f"ass={ass_filename}"
            )

    async def burn_subtitles_to_video(
        self,
        video_path: Path,
        ass_subtitle_path: Path,
        output_video_path: Path,
        mask_original_sub: bool = True,
        clean_chinese_mode: str = "cinema_bars",
        top_mask_pct: float = 0.11,
        bottom_mask_pct: float = 0.15,
        gpu_device_id: int = 0
    ) -> Path:
        """Burns ASS subtitles into video using auto-detected GPU hardware acceleration or libx264."""
        output_video_path.parent.mkdir(parents=True, exist_ok=True)
        ffmpeg_bin = settings.get_ffmpeg_bin()
        
        if self.is_ffmpeg_available():
            # Use relative filename with cwd to prevent Windows colon/drive letter parsing errors in FFmpeg filtergraph
            ass_filename = ass_subtitle_path.name
            ass_dir = ass_subtitle_path.parent

            vf_filter = self.build_video_filter(
                ass_filename=ass_filename,
                clean_chinese_mode=clean_chinese_mode,
                mask_original_sub=mask_original_sub,
                top_mask_pct=top_mask_pct,
                bottom_mask_pct=bottom_mask_pct
            )

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
            ffmpeg_bin = settings.get_ffmpeg_bin()
            cmd = [
                ffmpeg_bin,
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
