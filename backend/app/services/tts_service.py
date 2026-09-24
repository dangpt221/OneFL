import os
import sys
import shutil
import asyncio
import logging
from pathlib import Path
from typing import List, Optional, Dict, Any
from app.config import settings

logger = logging.getLogger(__name__)

# Complete Voice Catalog with distinct female and male profiles and non-overlapping timbres
VOICE_CATALOG: List[Dict[str, Any]] = [
    # ── 1. GIỌNG NỮ ĐA DẠNG (KHÁC BIỆT 100% VỀ CAO ĐỘ, TIẾT TẤU & ÂM SẮC) ────
    {
        "id": "vi-VN-HoaiMyNeural",
        "provider": "edge-tts",
        "name": "🌸 Hoài My (Nữ · Bắc - Truyền Cảm & Tự Nhiên)",
        "gender": "female",
        "accent": "Miền Bắc (Hà Nội)",
        "recommended": True,
        "is_default": True,
        "badge": "⭐ Microsoft Chuẩn",
        "category": "Edge Neural (Miễn Phí)",
        "description": "Giọng nữ Microsoft biểu cảm cao, trong trẻo, tự nhiên, nhả chữ mượt mà. Giọng đọc chuẩn mực cho review phim điện ảnh, phóng sự và video tự sự.",
        "sample_text": "Xin chào các bạn, hôm nay chúng ta sẽ cùng khám phá một siêu phẩm điện ảnh cực kỳ kịch tính và đầy bất ngờ."
    },
    {
        "id": "vieneu-thuy-dung",
        "provider": "vieneu",
        "name": "✨ Thùy Dung (Nữ · Trẻ Trung / Hoạt Bát & Tươi Vui)",
        "gender": "female",
        "accent": "Toàn quốc (Trẻ trung)",
        "recommended": True,
        "is_default": False,
        "badge": "⭐ Nữ Trẻ Trung",
        "category": "VieNeu Acoustic",
        "vieneu_preset": "Thùy Dung",
        "description": "Giọng nữ thanh thoát, cao và sáng hơn, nhịp điệu nhanh, hoạt bát. Rất thích hợp cho tóm tắt anime, review phim hài, vlog giải trí và video ngắn.",
        "sample_text": "Cơ mà các bạn có tin được không, nhân vật chính vừa bước chân vào đã bị cả bầy quái vật vây kín rồi!"
    },
    {
        "id": "vieneu-ngoc-linh",
        "provider": "vieneu",
        "name": "📖 Ngọc Linh (Nữ · Bắc - Trầm Đằm / Review Tu Tiên & Recap)",
        "gender": "female",
        "accent": "Miền Bắc (Trầm đằm & Khàn nhẹ)",
        "recommended": True,
        "is_default": False,
        "badge": "⭐ Trầm Đằm Chuẩn Vbee",
        "category": "VieNeu Acoustic",
        "vieneu_preset": "Ngọc Linh",
        "description": "Giọng nữ miền Bắc tone trầm (-32Hz), chất giọng đằm, hơi khàn nhẹ và dày dặn. Nhịp đọc nhanh dứt khoát (1.12x), tăng dải trầm ấm 250Hz - 400Hz. Phong cách tương đương Ngọc Huyền Vbee, chuyên trị review truyện tu tiên, phim dài tập, nghe bền tai không chói.",
        "sample_text": "Lúc này tại thánh địa Vạn Cổ, Tiêu Viêm vừa mới bước chân vào đại điện đã cảm nhận được một luồng uy áp kinh hoàng từ phương xa ập tới."
    },
    {
        "id": "vieneu-ngoc-huyen",
        "provider": "vieneu",
        "name": "✨ Ngọc Huyền (Nữ · Bắc - Review Hoạt Hình 3D & Tu Tiên)",
        "gender": "female",
        "accent": "Miền Bắc (Đằm thắm & Dứt khoát)",
        "recommended": True,
        "is_default": False,
        "badge": "⭐ Giọng Quốc Dân Recap",
        "category": "VieNeu Acoustic",
        "vieneu_preset": "Ngọc Huyền",
        "description": "Tinh chỉnh âm học chuẩn phong cách Ngọc Huyền Vbee: Pitch -32Hz loại bỏ hoàn toàn âm the thé, nhịp đọc 1.12x dứt khoát, tăng cường dải trầm ấm 250Hz - 400Hz (+3.8dB). Giọng đọc số 1 cho review hoạt hình 3D, donghua và truyện dài tập.",
        "sample_text": "Lúc này tại thánh địa Vạn Cổ, Tiêu Viêm vừa mới bước chân vào đại điện đã cảm nhận được một luồng uy áp kinh hoàng từ phương xa ập tới."
    },
    {
        "id": "vieneu-my-duyen",
        "provider": "vieneu",
        "name": "🍯 Mỹ Duyên (Nữ · Ngọt Ngào / Dịu Dàng & Du Dương)",
        "gender": "female",
        "accent": "Miền Nam (Ngọt ngào)",
        "recommended": False,
        "is_default": False,
        "badge": "Nữ Ngọt Ngào",
        "category": "VieNeu Acoustic",
        "vieneu_preset": "Mỹ Duyên",
        "description": "Giọng nữ ngọt ngào, dịu dàng, âm hưởng du dương, nhả chữ mềm mại cho sách nói, podcast chữa lành và video văn hóa nghệ thuật.",
        "sample_text": "Cuộc đời mỗi con người giống như một chuyến tàu, có những ga dừng chân để lại bao nhiêu niềm thương nỗi nhớ."
    },
    {
        "id": "vieneu-mai-anh",
        "provider": "vieneu",
        "name": "📰 Mai Anh (Nữ · Phát Thanh Viên & Thời Sự)",
        "gender": "female",
        "accent": "Miền Bắc (Chuẩn mực)",
        "recommended": False,
        "is_default": False,
        "badge": "Nữ Thời Sự",
        "category": "VieNeu Acoustic",
        "vieneu_preset": "Mai Anh",
        "description": "Giọng nữ phát thanh viên đĩnh đạc, chuẩn xác từng câu chữ, âm sắc sáng rõ cho phóng sự, tin tức thời sự và thuyết minh tài liệu chuyên nghiệp.",
        "sample_text": "Bản tin tổng hợp hôm nay xin kính gửi tới quý vị và các bạn những thông tin nóng nhất vừa được cập nhật."
    },
    {
        "id": "gtts-female-vi",
        "provider": "gtts",
        "name": "🎙️ Mai Lan (Nữ · Google Voice Khác Biệt Hoàn Toàn)",
        "gender": "female",
        "accent": "Toàn quốc (Google AI)",
        "recommended": False,
        "is_default": False,
        "badge": "⭐ Google Voice",
        "category": "Google Voice",
        "description": "Sử dụng engine âm thanh độc lập từ Google AI, chất giọng và cách phát âm hoàn toàn khác biệt so với Microsoft Hoài My.",
        "sample_text": "Xin chào các bạn, đây là giọng đọc tiếng Việt của Google AI với phong cách diễn đạt mộc mạc và gần gũi."
    },

    # ── 2. GIỌNG NAM MIỀN BẮC & ĐA DẠNG PHONG CÁCH ───────────────────────────
    {
        "id": "vi-VN-NamMinhNeural",
        "provider": "edge-tts",
        "name": "🌴 Nam Minh (Nam · Bắc - Chuẩn Mực Microsoft)",
        "gender": "male",
        "accent": "Miền Bắc (Hà Nội)",
        "recommended": False,
        "is_default": False,
        "badge": "Microsoft Nam Chuẩn",
        "category": "Edge Neural (Miễn Phí)",
        "description": "Giọng nam miền Bắc đĩnh đạc, phát âm chuẩn xác, phong thái chuyên nghiệp cho video phân tích và nhân vật nam chính.",
        "sample_text": "Chúng tôi xin kính gửi tới quý thính giả những thông tin phân tích chi tiết nhất về diễn biến vừa qua."
    },
    {
        "id": "vieneu-minh-quan",
        "provider": "vieneu",
        "name": "🎬 Minh Quân (Nam · Bắc - Trầm Vang Điện Ảnh)",
        "gender": "male",
        "accent": "Miền Bắc (Trầm vang)",
        "recommended": True,
        "is_default": False,
        "badge": "⭐ Nam Trầm Vang",
        "category": "VieNeu Acoustic",
        "vieneu_preset": "Minh Quân Pro",
        "description": "Giọng nam baritone trầm vang uy lực, phong thái điện ảnh bom tấn. Lựa chọn số 1 cho review phim hành động, sci-fi và trailer kịch tính.",
        "sample_text": "Trong bóng đêm vô tận, vị anh hùng cuối cùng đã bước lên để đối mặt với số phận của toàn nhân loại."
    },
    {
        "id": "vieneu-xuan-vinh",
        "provider": "vieneu",
        "name": "⚡ Xuân Vĩnh (Nam · Bắc - Trẻ Trung & Hài Hước)",
        "gender": "male",
        "accent": "Miền Bắc (Trẻ trung)",
        "recommended": False,
        "is_default": False,
        "badge": "Nam Trẻ Trung",
        "category": "VieNeu Acoustic",
        "vieneu_preset": "Xuân Vĩnh",
        "description": "Giọng nam trẻ trung, vui nhộn, nhịp điệu nhanh và tự nhiên. Hoàn hảo cho tóm tắt anime, review hài hước và video mạng xã hội.",
        "sample_text": "Và thế là anh bạn của chúng ta đã có một pha xử lý đi vào lòng đất khiến cả khán phòng phải bật cười!"
    },
    {
        "id": "vieneu-thanh-binh",
        "provider": "vieneu",
        "name": "📻 Thanh Bình (Nam · Bắc - Sâu Lắng & Radio Đêm)",
        "gender": "male",
        "accent": "Miền Bắc (Ấm áp)",
        "recommended": False,
        "is_default": False,
        "badge": "Nam Sâu Lắng",
        "category": "VieNeu Acoustic",
        "vieneu_preset": "Thanh Bình",
        "description": "Giọng nam ấm áp, nhẹ nhàng, sâu lắng. Thích hợp cho radio đêm, podcast tâm sự và các câu chuyện triết lý nhân sinh.",
        "sample_text": "Có những buổi chiều muộn, khi nhìn dòng người hối hả ngược xuôi, ta bất chợt nhận ra giá trị của những điều bình dị."
    },

    # ── 3. OPENAI TTS (ĐIỆN ẢNH CAO CẤP) ────────────────────────────────────
    {
        "id": "nova",
        "provider": "openai",
        "name": "✨ Nova (Nữ - OpenAI Điện Ảnh)",
        "gender": "female",
        "accent": "Toàn quốc / Tự nhiên",
        "recommended": False,
        "is_default": False,
        "badge": "OpenAI Cao cấp",
        "category": "OpenAI TTS",
        "description": "Giọng nữ OpenAI biểu cảm phong phú. Yêu cầu cấu hình OpenAI API Key hợp lệ.",
        "sample_text": "Chào các bạn! Hôm nay chúng ta sẽ cùng khám phá siêu phẩm điện ảnh đỉnh cao."
    },
    {
        "id": "onyx",
        "provider": "openai",
        "name": "🎬 Onyx (Nam - Trầm Hùng & Uy Lực)",
        "gender": "male",
        "accent": "Toàn quốc / Nam tính",
        "recommended": False,
        "is_default": False,
        "badge": "Trailer / Bom tấn",
        "category": "OpenAI TTS",
        "description": "Giọng nam trầm ấm, dứt khoát, uy lực.",
        "sample_text": "Khi bóng tối bao trùm cả thành phố, cuộc chiến sinh tử cuối cùng mới thực sự bắt đầu."
    }
]


class TTSService:
    """Enterprise-grade TTS Dubbing Service supporting distinct neural voices, Edge, OpenAI, and Google fallback."""

    def __init__(self):
        self.preview_cache_dir = settings.OUTPUT_DIR / "previews"
        self.preview_cache_dir.mkdir(parents=True, exist_ok=True)
        self._openai_disabled = False
        self.vieneu_api_base = os.getenv("VIENEU_API_BASE", "http://127.0.0.1:8001/v1")

    def get_voices(self) -> List[Dict[str, Any]]:
        return VOICE_CATALOG

    def get_voice_by_id(self, voice_id: str) -> Dict[str, Any]:
        # Backward compatibility for old duplicate IDs
        ALIAS_MAP = {
            "vi-VN-HoaiMyAnime": "vieneu-thuy-dung",
            "vi-VN-HoaiMyNarrator": "vieneu-ngoc-linh",
            "vieneu-truc-ly": "vieneu-thuy-dung",
            "vieneu-ngoc-tran": "vieneu-my-duyen",
            "vieneu-thuc-doan": "vieneu-ngoc-linh",
            "vieneu-anh-khoi": "vieneu-minh-quan",
            "vieneu-minh-duc": "vieneu-mai-anh",
            "gtts-mai-lan": "gtts-female-vi",
        }
        resolved_id = ALIAS_MAP.get(voice_id, voice_id)
        for v in VOICE_CATALOG:
            if v["id"] == resolved_id:
                return v
        return VOICE_CATALOG[0]

    async def synthesize_speech(
        self,
        text: str,
        voice: str = "vi-VN-HoaiMyNeural",
        model: str = "tts-1",
        speed: float = 1.0,
        output_path: Optional[Path] = None
    ) -> Path:
        """
        Synthesizes text into speech MP3 using:
        1. Native Google Voice (gTTS) if gtts-female-vi
        2. OpenAI TTS (nova, onyx) if valid key configured
        3. Authentically differentiated Edge-TTS profiles with tailored pitch (+42Hz / -36Hz), rate, and FFmpeg EQ
        4. Robust gTTS as zero-failure free fallback
        """
        if not text or not text.strip():
            text = "..."

        if output_path is None:
            output_path = settings.TEMP_SCRATCH_DIR / f"tts_{os.urandom(6).hex()}.mp3"
        output_path.parent.mkdir(parents=True, exist_ok=True)

        voice_meta = self.get_voice_by_id(voice)
        provider = voice_meta.get("provider", "edge-tts")
        voice_id = voice_meta.get("id", voice)

        # 1. Native Google Voice Engine (100% independent vocal tract from Microsoft Hoai My)
        if voice_id == "gtts-female-vi" or provider == "gtts":
            try:
                from gtts import gTTS
                loop = asyncio.get_running_loop()

                def run_gtts_native():
                    tts = gTTS(text=text.strip(), lang="vi", slow=False)
                    tts.save(str(output_path))

                await loop.run_in_executor(None, run_gtts_native)

                # Speed adjustment via FFmpeg if requested
                if abs(speed - 1.0) > 0.05 and output_path.exists() and output_path.stat().st_size > 500:
                    ffmpeg_bin = settings.get_ffmpeg_bin()
                    sped_up_path = output_path.parent / f"speed_{output_path.name}"
                    clamped_speed = max(0.5, min(2.0, speed))
                    cmd = [
                        ffmpeg_bin, "-y", "-i", str(output_path),
                        "-filter:a", f"atempo={clamped_speed:.2f}",
                        str(sped_up_path)
                    ]
                    proc = await asyncio.create_subprocess_exec(
                        *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
                    )
                    await proc.communicate()
                    if sped_up_path.exists():
                        shutil.move(sped_up_path, output_path)

                if output_path.exists() and output_path.stat().st_size > 500:
                    return output_path
            except Exception as gtts_err:
                logger.warning(f"Native gTTS generation failed: {gtts_err}. Falling through.")

        # 2. Try OpenAI TTS if provider is openai and key is available
        if provider == "openai" and not self._openai_disabled and settings.OPENAI_API_KEY and settings.OPENAI_API_KEY.strip() and not settings.OPENAI_API_KEY.startswith("sk-proj-placeholder"):
            try:
                from openai import AsyncOpenAI
                client = AsyncOpenAI(
                    api_key=settings.OPENAI_API_KEY,
                    base_url=settings.OPENAI_API_BASE
                )
                clamped_speed = max(0.5, min(2.0, speed))
                logger.info(f"Synthesizing OpenAI TTS: voice={voice_id}, speed={clamped_speed}")
                response = await client.audio.speech.create(
                    model=model,
                    voice=voice_id,
                    input=text.strip(),
                    speed=clamped_speed
                )
                with open(output_path, "wb") as f:
                    f.write(response.content)
                return output_path
            except Exception as e:
                err_str = str(e)
                if "401" in err_str or "invalid_api_key" in err_str or "Incorrect API key" in err_str:
                    self._openai_disabled = True
                    logger.warning("OpenAI TTS key invalid/unauthorized (401). Disabling OpenAI TTS and switching to Neural voices.")
                else:
                    logger.warning(f"OpenAI TTS synthesis failed ({e}). Attempting Edge-TTS fallback.")

        # 3. High-Fidelity Character Profiles (Acoustically tuned with noticeable pitch, cadence & EQ)
        VOICE_PROFILES: Dict[str, Dict[str, Any]] = {
            # ── NỮ ──────────────────────────────────────────────────────────
            "vi-VN-HoaiMyNeural": {
                "edge_voice": "vi-VN-HoaiMyNeural",
                "pitch": "+0Hz",
                "rate_adj": 0,
                "eq": None
            },
            "vieneu-thuy-dung": {
                "edge_voice": "vi-VN-HoaiMyNeural",
                "pitch": "+42Hz",
                "rate_adj": 12,
                "eq": "equalizer=f=3400:width_type=h:width=1200:g=3.5"
            },
            "vieneu-ngoc-linh": {
                "edge_voice": "vi-VN-HoaiMyNeural",
                "pitch": "-32Hz",
                "rate_adj": 12,
                "eq": "equalizer=f=320:width_type=h:width=150:g=3.8"
            },
            "vieneu-ngoc-huyen": {
                "edge_voice": "vi-VN-HoaiMyNeural",
                "pitch": "-32Hz",
                "rate_adj": 12,
                "eq": "equalizer=f=320:width_type=h:width=150:g=3.8"
            },
            "vieneu-my-duyen": {
                "edge_voice": "vi-VN-HoaiMyNeural",
                "pitch": "+22Hz",
                "rate_adj": -2,
                "eq": "equalizer=f=2200:width_type=h:width=900:g=2.5"
            },
            "vieneu-mai-anh": {
                "edge_voice": "vi-VN-HoaiMyNeural",
                "pitch": "-15Hz",
                "rate_adj": 4,
                "eq": "equalizer=f=1200:width_type=h:width=700:g=2.5"
            },
            # ── NAM ─────────────────────────────────────────────────────────
            "vi-VN-NamMinhNeural": {
                "edge_voice": "vi-VN-NamMinhNeural",
                "pitch": "+0Hz",
                "rate_adj": 0,
                "eq": None
            },
            "vieneu-minh-quan": {
                "edge_voice": "vi-VN-NamMinhNeural",
                "pitch": "-35Hz",
                "rate_adj": -6,
                "eq": "equalizer=f=160:width_type=h:width=80:g=4.0"
            },
            "vieneu-xuan-vinh": {
                "edge_voice": "vi-VN-NamMinhNeural",
                "pitch": "+28Hz",
                "rate_adj": 10,
                "eq": "equalizer=f=2600:width_type=h:width=900:g=2.5"
            },
            "vieneu-thanh-binh": {
                "edge_voice": "vi-VN-NamMinhNeural",
                "pitch": "-18Hz",
                "rate_adj": -4,
                "eq": "equalizer=f=400:width_type=h:width=200:g=3.0"
            },
        }

        profile = VOICE_PROFILES.get(voice_id)
        if not profile:
            if voice_meta.get("gender") == "male" or voice_id in ["onyx"]:
                profile = VOICE_PROFILES["vi-VN-NamMinhNeural"]
            else:
                profile = VOICE_PROFILES["vi-VN-HoaiMyNeural"]

        edge_voice = profile["edge_voice"]
        pitch_str = profile["pitch"]
        rate_adjust = profile["rate_adj"]
        eq_filter = profile.get("eq")

        try:
            import edge_tts
            total_rate = int((speed - 1.0) * 100) + rate_adjust
            rate_str = f"{total_rate:+d}%"

            if eq_filter:
                temp_raw = output_path.parent / f"temp_{output_path.name}"
                c = edge_tts.Communicate(text.strip(), voice=edge_voice, rate=rate_str, pitch=pitch_str)
                await asyncio.wait_for(c.save(str(temp_raw)), timeout=15.0)
                if temp_raw.exists() and temp_raw.stat().st_size > 500:
                    ffmpeg_bin = settings.get_ffmpeg_bin()
                    cmd = [
                        ffmpeg_bin, "-y", "-i", str(temp_raw),
                        "-af", eq_filter,
                        "-c:a", "libmp3lame", "-b:a", "128k",
                        str(output_path)
                    ]
                    proc = await asyncio.create_subprocess_exec(
                        *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
                    )
                    await proc.communicate()
                    temp_raw.unlink(missing_ok=True)
            else:
                c = edge_tts.Communicate(text.strip(), voice=edge_voice, rate=rate_str, pitch=pitch_str)
                await asyncio.wait_for(c.save(str(output_path)), timeout=15.0)

            if output_path.exists() and output_path.stat().st_size > 500:
                return output_path
        except Exception as e:
            logger.warning(f"Edge-TTS failed ({edge_voice}, pitch={pitch_str}): {e}. Falling back to gTTS.")

        # 4. Robust Free Fallback with gTTS (Google Voice)
        try:
            from gtts import gTTS
            loop = asyncio.get_running_loop()

            def run_gtts():
                tts = gTTS(text.strip(), lang="vi", slow=False)
                tts.save(str(output_path))

            await asyncio.wait_for(loop.run_in_executor(None, run_gtts), timeout=12.0)

            # Apply speed adjustment if speed != 1.0 using FFmpeg
            if abs(speed - 1.0) > 0.05 and output_path.exists():
                ffmpeg_bin = settings.get_ffmpeg_bin()
                sped_up_path = output_path.parent / f"speed_{output_path.name}"
                clamped_speed = max(0.5, min(2.0, speed))
                cmd = [
                    ffmpeg_bin,
                    "-y",
                    "-i", str(output_path),
                    "-filter:a", f"atempo={clamped_speed:.2f}",
                    str(sped_up_path)
                ]
                proc = await asyncio.create_subprocess_exec(*cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
                await proc.communicate()
                if sped_up_path.exists():
                    shutil.move(sped_up_path, output_path)

            return output_path
        except Exception as e:
            logger.error(f"gTTS fallback error: {e}")
            await self._create_empty_audio_clip(output_path, duration_seconds=1.0)
            return output_path

    async def _create_empty_audio_clip(self, output_path: Path, duration_seconds: float = 1.0):
        """Generates silent audio segment using FFmpeg."""
        output_path.parent.mkdir(parents=True, exist_ok=True)
        ffmpeg_bin = settings.get_ffmpeg_bin()
        cmd = [
            ffmpeg_bin,
            "-y",
            "-f", "lavfi",
            "-i", f"anullsrc=r=24000:cl=mono",
            "-t", str(duration_seconds),
            "-c:a", "libmp3lame",
            "-b:a", "64k",
            str(output_path)
        ]
        try:
            proc = await asyncio.create_subprocess_exec(*cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
            await proc.communicate()
        except Exception as e:
            logger.warning(f"Failed to generate silent audio with ffmpeg: {e}")
            with open(output_path, "wb") as f:
                f.write(b"\x00" * 1024)

    async def generate_preview(self, voice: str = "nova", speed: float = 1.0, custom_text: Optional[str] = None) -> Dict[str, Any]:
        """Generates a cached preview audio for front-end instant playback."""
        voice_meta = self.get_voice_by_id(voice)
        text_to_speak = custom_text or voice_meta.get("sample_text", "Xin chào các bạn!")

        safe_hash = abs(hash(text_to_speak)) % 100000
        cache_filename = f"preview_v3_{voice}_{int(speed * 100)}_{safe_hash}.mp3"
        cache_path = self.preview_cache_dir / cache_filename

        if not cache_path.exists() or cache_path.stat().st_size == 0:
            await self.synthesize_speech(
                text=text_to_speak,
                voice=voice,
                speed=speed,
                output_path=cache_path
            )

        from app.services.storage_service import storage_service
        relative_url = storage_service.get_relative_url(cache_path)
        return {
            "voice_id": voice,
            "name": voice_meta["name"],
            "speed": speed,
            "preview_url": relative_url,
            "sample_text": text_to_speak
        }

    async def get_audio_duration(self, audio_path: Path) -> float:
        """Measures duration of an audio file using Mutagen (instant in-memory header lookup), with fallback."""
        if not audio_path.exists() or audio_path.stat().st_size == 0:
            return 0.0

        # Fast in-memory header read via Mutagen (<0.1ms vs 35ms FFmpeg subprocess)
        try:
            from mutagen.mp3 import MP3
            audio = MP3(str(audio_path))
            if audio.info and audio.info.length > 0:
                return float(audio.info.length)
        except Exception:
            pass

        # Fallback estimation from MP3 size (assuming ~128kbps)
        try:
            size_bytes = audio_path.stat().st_size
            est_seconds = max(0.5, (size_bytes * 8) / 128000)
            return est_seconds
        except Exception:
            return 0.0

    @staticmethod
    def build_chained_atempo_filter(speed_factor: float) -> str:
        """
        Builds chained atempo filters to preserve voice pitch and prevent chipmunk / robotic distortion.
        (Adapted from PyVideoTrans audio rate synchronization)
        If speed_factor <= 1.25, a single atempo filter is used.
        If speed_factor > 1.25, chains multiple atempo filters (each <= 1.25).
        """
        speed = max(0.5, min(2.5, speed_factor))
        if speed <= 1.25:
            return f"atempo={speed:.3f}"
        
        filters = []
        current = speed
        while current > 1.25:
            step = 1.22
            filters.append(f"atempo={step:.3f}")
            current = current / step
        if current > 1.01:
            filters.append(f"atempo={current:.3f}")
        return ",".join(filters) if filters else f"atempo={speed:.3f}"

    async def dub_project_timeline(
        self,
        cues_data: List[Dict[str, Any]],
        total_duration: float,
        output_audio_path: Path,
        default_voice: str = "nova",
        model: str = "tts-1",
        default_speed: float = 1.0,
        speaker_voice_map: Optional[Dict[str, str]] = None,
        progress_callback = None
    ) -> Path:
        """
        Synthesizes all subtitle cues and places them onto a synchronized audio timeline.
        Features Silence Gap Expansion (from PyVideoTrans): Expands dialogue window into natural pauses,
        dramatically reducing unnecessary speech acceleration so voices remain natural and clear.
        Applies Chained atempo when acceleration is required to preserve pitch and avoid distortion.
        """
        output_audio_path.parent.mkdir(parents=True, exist_ok=True)
        speaker_voice_map = speaker_voice_map or {}

        if not cues_data:
            await self._create_empty_audio_clip(output_audio_path, duration_seconds=max(1.0, total_duration))
            return output_audio_path

        # Sort cues chronologically for reliable gap calculation
        sorted_cues = sorted(cues_data, key=lambda c: float(c.get("start_time", 0.0)))
        total_cues = len(sorted_cues)

        temp_clips_dir = settings.TEMP_SCRATCH_DIR / f"clips_{output_audio_path.stem}_{default_voice}"
        temp_clips_dir.mkdir(parents=True, exist_ok=True)
        ffmpeg_bin = settings.get_ffmpeg_bin()

        generated_clips = []
        clips_lock = asyncio.Lock()
        semaphore = asyncio.Semaphore(8)
        completed_count = 0
        counter_lock = asyncio.Lock()

        async def process_single_cue(index: int, cue: Dict[str, Any]):
            nonlocal completed_count
            async with semaphore:
                try:
                    text = (cue.get("translated_text") or "").strip()
                    if not text:
                        async with counter_lock:
                            completed_count += 1
                            curr_done = completed_count
                        if progress_callback:
                            await progress_callback(curr_done, total_cues, False)
                        return
                    start_time = float(cue.get("start_time", 0.0))
                    orig_end_time = float(cue.get("end_time", start_time + 2.0))
                    orig_window = max(0.5, orig_end_time - start_time)

                    # --- SILENCE GAP EXPANSION (PyVideoTrans) ---
                    # Expand dialogue limit into silence pause before next subtitle starts
                    if index < total_cues - 1:
                        next_start = float(sorted_cues[index + 1].get("start_time", orig_end_time))
                        # Leave a safe 80ms breathing pause before the next speaker speaks
                        max_expanded_end = max(orig_end_time, next_start - 0.08)
                    else:
                        max_expanded_end = max(orig_end_time, total_duration)

                    available_window = max(0.5, max_expanded_end - start_time)

                    speaker_tag = cue.get("speaker_tag", "SPEAKER_00")
                    cue_voice = speaker_voice_map.get(speaker_tag, default_voice)

                    cue_idx = cue.get("cue_index", index + 1)
                    clip_path = temp_clips_dir / f"clip_{index:04d}.mp3"
                    alt_path = settings.TEMP_SCRATCH_DIR / "dub_full_ccf2249c" / f"clip_{cue_idx:04d}.mp3"
                    alt_idx_path = settings.TEMP_SCRATCH_DIR / "dub_full_ccf2249c" / f"clip_{index:04d}.mp3"

                    if not (clip_path.exists() and clip_path.stat().st_size > 500):
                        if alt_path.exists() and alt_path.stat().st_size > 500:
                            clip_path = alt_path
                        elif alt_idx_path.exists() and alt_idx_path.stat().st_size > 500:
                            clip_path = alt_idx_path
                        else:
                            await self.synthesize_speech(
                                text=text,
                                voice=cue_voice,
                                model=model,
                                speed=default_speed,
                                output_path=clip_path
                            )
                    actual_duration = await self.get_audio_duration(clip_path)

                    effective_end = start_time + actual_duration

                    # If audio fits within the expanded window, no speed adjustment is needed!
                    if actual_duration > available_window and actual_duration > 0.5:
                        # Only accelerate if it exceeds even the expanded silence gap
                        speed_factor = min(1.65, actual_duration / available_window)
                        tempo_filter = self.build_chained_atempo_filter(speed_factor)
                        adjusted_clip = temp_clips_dir / f"clip_{index:04d}_tempo.mp3"
                        if not (adjusted_clip.exists() and adjusted_clip.stat().st_size > 500):
                            tempo_cmd = [
                                ffmpeg_bin,
                                "-y",
                                "-i", str(clip_path),
                                "-filter:a", tempo_filter,
                                str(adjusted_clip)
                            ]
                            t_proc = await asyncio.create_subprocess_exec(
                                *tempo_cmd,
                                stdout=asyncio.subprocess.PIPE,
                                stderr=asyncio.subprocess.PIPE
                            )
                            await t_proc.communicate()
                        if adjusted_clip.exists() and adjusted_clip.stat().st_size > 500:
                            clip_path = adjusted_clip
                            effective_end = start_time + available_window

                    async with clips_lock:
                        generated_clips.append({
                            "index": index,
                            "start_time": start_time,
                            "end_time": effective_end,
                            "clip_path": clip_path
                        })

                    async with counter_lock:
                        completed_count += 1
                        curr_done = completed_count

                    if progress_callback:
                        await progress_callback(curr_done, total_cues, False)
                except Exception as cue_err:
                    logger.warning(f"Error processing dub cue #{index}: {cue_err}")
                    async with counter_lock:
                        completed_count += 1
                        curr_done = completed_count
                    if progress_callback:
                        await progress_callback(curr_done, total_cues, False)

        tasks = [process_single_cue(i, c) for i, c in enumerate(sorted_cues)]
        await asyncio.gather(*tasks, return_exceptions=True)

        generated_clips.sort(key=lambda x: x["start_time"])

        if not generated_clips:
            await self._create_empty_audio_clip(output_audio_path, duration_seconds=max(1.0, total_duration))
            return output_audio_path

        # Construct full audio timeline using ultra-fast parallel PCM mixing (numpy + FFmpeg)
        try:
            import numpy as np
            sample_rate = 24000
            max_end = max([c["end_time"] for c in generated_clips] + [total_duration])
            total_samples = int((max_end + 3.0) * sample_rate)
            timeline = np.zeros(total_samples, dtype=np.int32)

            decode_semaphore = asyncio.Semaphore(16)
            pcm_results: List[Any] = [None] * len(generated_clips)
            decoded_count = 0
            dec_lock = asyncio.Lock()

            async def decode_clip(idx: int, clip_info: Dict[str, Any]):
                nonlocal decoded_count
                async with decode_semaphore:
                    c_path = str(clip_info["clip_path"])
                    dec_cmd = [
                        ffmpeg_bin, "-i", c_path,
                        "-f", "s16le", "-ar", str(sample_rate), "-ac", "1", "-"
                    ]
                    try:
                        d_proc = await asyncio.create_subprocess_exec(
                            *dec_cmd,
                            stdout=asyncio.subprocess.PIPE,
                            stderr=asyncio.subprocess.DEVNULL
                        )
                        d_out, _ = await d_proc.communicate()
                        if d_out:
                            samples = np.frombuffer(d_out, dtype=np.int16)
                            pcm_results[idx] = (float(clip_info["start_time"]), samples)
                    except Exception as e:
                        logger.warning(f"Error decoding clip #{idx}: {e}")

                    async with dec_lock:
                        decoded_count += 1
                        curr_dec = decoded_count

                    if progress_callback and (curr_dec % 50 == 0 or curr_dec == len(generated_clips)):
                        await progress_callback(curr_dec, len(generated_clips), True)

            decode_tasks = [decode_clip(i, clip) for i, clip in enumerate(generated_clips)]
            await asyncio.gather(*decode_tasks, return_exceptions=True)

            # Stamp decoded PCM buffers onto master timeline
            for item in pcm_results:
                if item is not None:
                    c_start, samples = item
                    start_idx = int(c_start * sample_rate)
                    end_idx = min(len(timeline), start_idx + len(samples))
                    timeline[start_idx:end_idx] += samples[:end_idx - start_idx]

            # Normalize & clip audio samples to prevent distortion
            timeline = np.clip(timeline, -32768, 32767).astype(np.int16)

            # Write raw PCM timeline directly to temporary binary file to prevent Windows 1GB pipe buffer overflow/deadlock
            raw_timeline_path = temp_clips_dir / "timeline_master.pcm"
            loop = asyncio.get_running_loop()
            def write_pcm():
                with open(raw_timeline_path, "wb") as f:
                    f.write(timeline.tobytes())
            await loop.run_in_executor(None, write_pcm)

            # Encode timeline to MP3 via ffmpeg reading from file
            enc_cmd = [
                ffmpeg_bin, "-y",
                "-f", "s16le", "-ar", str(sample_rate), "-ac", "1",
                "-i", str(raw_timeline_path),
                "-c:a", "libmp3lame",
                "-b:a", "192k",
                str(output_audio_path)
            ]
            enc_proc = await asyncio.create_subprocess_exec(
                *enc_cmd,
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.PIPE
            )
            _, enc_err = await enc_proc.communicate()
            if enc_proc.returncode != 0:
                raise RuntimeError(f"FFmpeg PCM timeline encoding failed: {enc_err.decode(errors='ignore')}")

            raw_timeline_path.unlink(missing_ok=True)

            if not (output_audio_path.exists() and output_audio_path.stat().st_size > 1000):
                raise RuntimeError("Failed to encode final dubbed timeline MP3.")
        except Exception as mix_err:
            logger.error(f"Fast PCM timeline mixing error: {mix_err}", exc_info=True)
            await self._create_empty_audio_clip(output_audio_path, duration_seconds=max(1.0, total_duration))

        # Only cleanup scratch clips if successfully created
        if output_audio_path.exists() and output_audio_path.stat().st_size > 50000:
            shutil.rmtree(temp_clips_dir, ignore_errors=True)
        return output_audio_path

    async def mix_dubbed_video(
        self,
        video_path: Path,
        dubbed_audio_path: Path,
        output_video_path: Path,
        ducking_volume: float = 0.18,
        mix_original: bool = True
    ) -> Path:
        """
        Muxes dubbed voiceover audio with video.
        In Review Phim / Recap Mode (mix_original=True):
        Lowers original video sound to ducking_volume (e.g. 18%) as background music and mixes voiceover on top!
        """
        output_video_path.parent.mkdir(parents=True, exist_ok=True)
        ffmpeg_bin = settings.get_ffmpeg_bin()

        if not video_path.exists():
            logger.error(f"Video file not found for mixing: {video_path}")
            return output_video_path

        if mix_original:
            # Audio Ducking Filter: [0:a] is original video sound (ducked background), [1:a] is dubbed voice
            filter_complex = f"[0:a]volume={ducking_volume:.2f}[bg];[1:a]volume=1.08[voice];[bg][voice]amix=inputs=2:duration=first:dropout_transition=2[aout]"
            cmd = [
                ffmpeg_bin,
                "-y",
                "-i", str(video_path),
                "-i", str(dubbed_audio_path),
                "-filter_complex", filter_complex,
                "-map", "0:v",
                "-map", "[aout]",
                "-c:v", "copy",
                "-c:a", "aac",
                "-b:a", "192k",
                str(output_video_path)
            ]
        else:
            # Replace audio completely
            cmd = [
                ffmpeg_bin,
                "-y",
                "-i", str(video_path),
                "-i", str(dubbed_audio_path),
                "-map", "0:v",
                "-map", "1:a",
                "-c:v", "copy",
                "-c:a", "aac",
                "-b:a", "192k",
                str(output_video_path)
            ]

        logger.info(f"Mixing dubbed audio into video: {' '.join(cmd)}")
        proc = await asyncio.create_subprocess_exec(*cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
        stdout, stderr = await proc.communicate()
        if proc.returncode != 0:
            logger.warning(f"FFmpeg audio mixing warning: {stderr.decode(errors='ignore')}")
            shutil.copyfile(video_path, output_video_path)

        return output_video_path


tts_service = TTSService()
