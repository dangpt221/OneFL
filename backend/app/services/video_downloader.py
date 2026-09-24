import os
import re
import asyncio
import logging
from pathlib import Path
from typing import Dict, Any, Optional
import yt_dlp
from app.config import settings

logger = logging.getLogger(__name__)


class VideoDownloaderService:
    """Service to download videos from Bilibili, YouTube, Douyin, etc. using yt-dlp."""

    def __init__(self):
        self.ffmpeg_bin = settings.get_ffmpeg_bin()

    def detect_platform(self, url: str) -> str:
        """Detect platform from URL."""
        lower = url.lower()
        if "bilibili.com" in lower or "b23.tv" in lower:
            return "bilibili"
        elif "douyin.com" in lower or "tiktok.com" in lower:
            return "douyin"
        elif "youtube.com" in lower or "youtu.be" in lower:
            return "youtube"
        elif "kuaishou.com" in lower:
            return "kuaishou"
        return "generic"

    def get_suggested_source_language(self, platform: str) -> str:
        if platform in ["bilibili", "douyin", "kuaishou"]:
            return "zh"
        return "auto"

    def _get_base_ydl_opts(self) -> Dict[str, Any]:
        """Configure yt-dlp with appropriate headers and ffmpeg binary."""
        ffmpeg_exe = settings.get_ffmpeg_bin()

        opts = {
            "quiet": True,
            "no_warnings": True,
            "noplaylist": True,
            "socket_timeout": 30,
            "retries": 10,
            "fragment_retries": 10,
            "file_access_retries": 5,
            "extractor_retries": 5,
            "http_headers": {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
                "Referer": "https://www.bilibili.com/",
                "Origin": "https://www.bilibili.com",
            },
        }
        if ffmpeg_exe and os.path.exists(ffmpeg_exe):
            opts["ffmpeg_location"] = ffmpeg_exe
        return opts

    async def extract_info(self, url: str) -> Dict[str, Any]:
        """Extract metadata (Title, duration, thumbnail) without downloading video."""
        loop = asyncio.get_running_loop()
        platform = self.detect_platform(url)

        def _extract():
            ydl_opts = self._get_base_ydl_opts()
            ydl_opts["skip_download"] = True
            ydl_opts["extract_flat"] = True
            ydl_opts["noplaylist"] = True

            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)
                return info

        try:
            info = await loop.run_in_executor(None, _extract)
            title = info.get("title") or "Bilibili Video"
            duration = float(info.get("duration") or 0.0)
            thumbnail = info.get("thumbnail") or ""
            uploader = info.get("uploader") or info.get("channel") or ""

            return {
                "success": True,
                "url": url,
                "platform": platform,
                "title": title,
                "duration": duration,
                "thumbnail": thumbnail,
                "uploader": uploader,
                "suggested_source_language": self.get_suggested_source_language(platform)
            }
        except Exception as e:
            logger.warning(f"Failed to extract info from {url}: {e}")
            return {
                "success": False,
                "url": url,
                "platform": platform,
                "title": "Bilibili Video",
                "duration": 0.0,
                "thumbnail": "",
                "uploader": "",
                "suggested_source_language": self.get_suggested_source_language(platform),
                "error": str(e)
            }

    async def download_video(
        self,
        url: str,
        output_dir: Path,
        progress_callback = None
    ) -> Dict[str, Any]:
        """
        Downloads video and audio stream from Bilibili or other platforms,
        merging into a standard high-compatibility MP4 file.
        """
        output_dir.mkdir(parents=True, exist_ok=True)
        loop = asyncio.get_running_loop()
        platform = self.detect_platform(url)

        # File template
        out_tmpl = str(output_dir / "video_%(id)s.%(ext)s")

        ydl_opts = self._get_base_ydl_opts()
        ydl_opts.update({
            "format": "bestvideo[height<=720][ext=mp4]+bestaudio[ext=m4a]/bestvideo[height<=720]+bestaudio/bestvideo[height<=1080]+bestaudio/best[height<=720]/best",
            "outtmpl": out_tmpl,
            "merge_output_format": "mp4",
            "noplaylist": True,
            "concurrent_fragment_downloads": 8,
            "http_chunk_size": 10485760,
            "buffersize": 1048576,
        })

        if progress_callback:
            def ydl_hook(d):
                if d.get("status") == "downloading":
                    pct = 0.0
                    # Try percentage string first (most accurate in yt-dlp)
                    if d.get("_percent_str"):
                        try:
                            clean_str = re.sub(r'\x1b\[[0-9;]*m', '', d["_percent_str"]).replace('%', '').strip()
                            pct = float(clean_str)
                        except Exception:
                            pct = 0.0
                    if pct <= 0.0:
                        total = d.get("total_bytes") or d.get("total_bytes_estimate") or 0
                        downloaded = d.get("downloaded_bytes") or 0
                        if total > 0:
                            pct = (downloaded / total) * 100.0
                        elif d.get("fragment_count") and d.get("fragment_index"):
                            pct = (d["fragment_index"] / d["fragment_count"]) * 100.0

                    speed = re.sub(r'\x1b\[[0-9;]*m', '', d.get("_speed_str") or "").strip()
                    eta = re.sub(r'\x1b\[[0-9;]*m', '', d.get("_eta_str") or "").strip()
                    downloaded_str = re.sub(r'\x1b\[[0-9;]*m', '', d.get("_downloaded_bytes_str") or "").strip()
                    total_str = re.sub(r'\x1b\[[0-9;]*m', '', d.get("_total_bytes_str") or "").strip()

                    progress_info = {
                        "pct": min(100.0, max(0.0, round(pct, 1))),
                        "speed": speed,
                        "eta": eta,
                        "downloaded": downloaded_str,
                        "total": total_str
                    }

                    if loop.is_running():
                        asyncio.run_coroutine_threadsafe(progress_callback(progress_info), loop)

            ydl_opts["progress_hooks"] = [ydl_hook]

        def _download():
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
                filename = ydl.prepare_filename(info)
                # Ensure mp4 extension after merge
                merged_filename = os.path.splitext(filename)[0] + ".mp4"
                if os.path.exists(merged_filename):
                    final_path = Path(merged_filename)
                elif os.path.exists(filename):
                    final_path = Path(filename)
                else:
                    # Search output_dir for any downloaded video
                    files = list(output_dir.glob("video_*.*"))
                    final_path = files[0] if files else Path(filename)

                return {
                    "file_path": final_path,
                    "title": info.get("title") or "Bilibili Video",
                    "duration": float(info.get("duration") or 0.0),
                    "thumbnail": info.get("thumbnail") or ""
                }

        try:
            logger.info(f"Starting yt-dlp download for URL: {url} on platform: {platform}")
            result = await loop.run_in_executor(None, _download)
            logger.info(f"Successfully downloaded video to: {result['file_path']}")
            return {
                "success": True,
                "file_path": result["file_path"],
                "title": result["title"],
                "duration": result["duration"],
                "thumbnail": result["thumbnail"],
                "platform": platform
            }
        except Exception as e:
            logger.error(f"Download failed for {url}: {e}", exc_info=True)
            raise e


video_downloader = VideoDownloaderService()
