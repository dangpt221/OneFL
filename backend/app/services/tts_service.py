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
    # ── 1. GIỌNG NỮ ĐA DẠNG (KHÁC BIỆT VỀ CAO ĐỘ, TIẾT TẤU & ÂM SẮC) ────
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
        "category": "Edge Neural · Cấu hình âm sắc",
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
        "badge": "⭐ Trầm Đằm Tùy chỉnh âm sắc",
        "category": "Edge Neural · Cấu hình âm sắc",
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
        "category": "Edge Neural · Cấu hình âm sắc",
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
        "category": "Edge Neural · Cấu hình âm sắc",
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
        "category": "Edge Neural · Cấu hình âm sắc",
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
        "category": "Edge Neural · Cấu hình âm sắc",
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
        "category": "Edge Neural · Cấu hình âm sắc",
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
        "category": "Edge Neural · Cấu hình âm sắc",
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
    },
    {
        "id": "alloy",
        "provider": "openai",
        "name": "🎙️ Alloy (Trung Tính - Cân Bằng & Hiện Đại)",
        "gender": "neutral",
        "accent": "Chuẩn mực",
        "recommended": False,
        "is_default": False,
        "badge": "OpenAI Chuẩn",
        "category": "OpenAI TTS",
        "description": "Giọng đọc cân bằng, tự nhiên, nhả chữ rõ ràng cho phóng sự và bài giảng.",
        "sample_text": "Hôm nay chúng ta sẽ phân tích toàn diện về các tiến bộ công nghệ mới nhất."
    },
    {
        "id": "echo",
        "provider": "openai",
        "name": "📻 Echo (Nam - Trầm Ấm & Thuyết Minh)",
        "gender": "male",
        "accent": "Trầm ấm",
        "recommended": False,
        "is_default": False,
        "badge": "Thuyết Minh",
        "category": "OpenAI TTS",
        "description": "Giọng nam ấm áp, tròn vành rõ chữ, phù hợp với phim tài liệu và tự sự.",
        "sample_text": "Thời gian trôi qua, những câu chuyện lịch sử vẫn còn nguyên giá trị cho mai sau."
    },
    {
        "id": "fable",
        "provider": "openai",
        "name": "🎭 Fable (Nam - Kịch Tính & Cổ Tích)",
        "gender": "male",
        "accent": "Kịch tính",
        "recommended": False,
        "is_default": False,
        "badge": "Kể Chuyện",
        "category": "OpenAI TTS",
        "description": "Giọng nam biểu cảm kịch nghệ, tạo điểm nhấn sâu sắc cho kịch bản hư cấu.",
        "sample_text": "Ngày xửa ngày xưa, ở một vương quốc xa xôi nơi ánh bình minh không bao giờ tắt."
    },
    {
        "id": "shimmer",
        "provider": "openai",
        "name": "🌸 Shimmer (Nữ - Trong Sáng & Dịu Ngọt)",
        "gender": "female",
        "accent": "Trong trẻo",
        "recommended": False,
        "is_default": False,
        "badge": "Nữ Dịu Dàng",
        "category": "OpenAI TTS",
        "description": "Giọng nữ trong trẻo, êm dịu, phù hợp cho podcast thư giãn và nội dung nhẹ nhàng.",
        "sample_text": "Hãy cùng lắng đọng tâm hồn và tận hưởng những giai điệu êm đềm của buổi tối."
    }
]

# High-Fidelity Character Profiles (Acoustically tuned with noticeable pitch, cadence & EQ)
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

class TTSService:
    """Enterprise-grade TTS Dubbing Service supporting distinct neural voices, Edge, OpenAI, and Google fallback."""

    def __init__(self):
        self.preview_cache_dir = settings.OUTPUT_DIR / "previews"
        self.preview_cache_dir.mkdir(parents=True, exist_ok=True)
        self._openai_disabled = False

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
        # Fallback matching by display name or partial keyword
        v_lower = str(voice_id).lower()
        for v in VOICE_CATALOG:
            if v["name"].lower() == v_lower:
                return v
        if "gtts" in v_lower:
            for v in VOICE_CATALOG:
                if v.get("provider") == "gtts":
                    return v
        raise ValueError(f"Unknown voice ID: {voice_id}")


    async def synthesize_speech(
        self, text: str, voice: str = "vi-VN-HoaiMyNeural", model: str = "tts-1",
        speed: float = 1.0, output_path: Optional[Path] = None,
    ) -> Path:
        from app.services.media_process import run_media, probe_media
        from app.services.asr_service import ASRService
        if not text.strip() or len(text) > 10000 or not 0.5 <= speed <= 2.0:
            raise ValueError('Speech requires nonempty text (max 10000 characters) and speed 0.5?2.0')
        meta = self.get_voice_by_id(voice)
        voice_id, provider = meta['id'], meta['provider']
        output_path = output_path or settings.TEMP_SCRATCH_DIR / f'tts_{os.urandom(12).hex()}.mp3'
        output_path.parent.mkdir(parents=True, exist_ok=True)
        temporary = output_path.with_name(f'.{os.urandom(6).hex()}.mp3')
        try:
            if provider == 'openai':
                if not settings.OPENAI_API_KEY or 'DIEN_API_KEY' in settings.OPENAI_API_KEY:
                    raise RuntimeError('OpenAI voice requires a configured API key')
                from openai import AsyncOpenAI
                async with AsyncOpenAI(api_key=settings.OPENAI_API_KEY, base_url=settings.OPENAI_API_BASE, timeout=45) as client:
                    response = await client.audio.speech.create(model=model, voice=voice_id, input=text.strip(), speed=speed)
                    temporary.write_bytes(response.content)
            elif provider == 'gtts':
                from gtts import gTTS
                await ASRService._blocking(lambda: gTTS(text=text.strip(), lang='vi', slow=False, timeout=20).save(str(temporary)))
            else:
                import edge_tts
                profile = VOICE_PROFILES[voice_id]
                rate = f"{int((speed - 1.) * 100) + profile['rate_adj']:+d}%"
                last_error = None
                for attempt in range(3):
                    try:
                        speech = edge_tts.Communicate(text.strip(), voice=profile['edge_voice'], rate=rate, pitch=profile['pitch'])
                        await asyncio.wait_for(speech.save(str(temporary)), timeout=30)
                        await probe_media(temporary, require_audio=True)
                        last_error = None
                        break
                    except Exception as error:
                        last_error = error
                        logger.warning('TTS attempt %s failed for %s: %s', attempt + 1, voice_id, type(error).__name__)
                        if attempt < 2:
                            await asyncio.sleep(0.5 * (attempt + 1))
                if last_error:
                    raise RuntimeError(f'Speech generation failed for {voice_id}: {last_error}') from last_error
            filters = []
            if provider == 'gtts' and speed != 1.:
                filters.append(self.build_chained_atempo_filter(speed))
            profile = VOICE_PROFILES.get(voice_id, {})
            if profile.get('eq'):
                filters.append(profile['eq'])
            if filters:
                filtered = temporary.with_name(f'filtered_{temporary.name}')
                try:
                    await run_media([settings.get_ffmpeg_bin(), '-y', '-i', str(temporary), '-af', ','.join(filters), str(filtered)])
                    filtered.replace(temporary)
                finally:
                    filtered.unlink(missing_ok=True)
            await probe_media(temporary, require_audio=True)
            temporary.replace(output_path)
            return output_path
        finally:
            temporary.unlink(missing_ok=True)

    async def generate_preview(self, voice: str = "vi-VN-HoaiMyNeural", speed: float = 1., custom_text: Optional[str] = None, model: Optional[str] = None) -> Dict[str, Any]:
        import hashlib
        import json
        from app.services.media_process import probe_media
        from app.services.storage_service import storage_service
        meta = self.get_voice_by_id(voice)
        text = custom_text or meta['sample_text']
        model = model or settings.DEFAULT_TTS_MODEL
        key = hashlib.sha256(json.dumps(['v5', meta['id'], model, speed, text], ensure_ascii=False).encode()).hexdigest()
        from app.security import current_user
        directory = settings.OUTPUT_DIR / 'previews' / current_user.get()
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / f'{key}.mp3'
        valid = False
        if path.exists():
            try:
                await probe_media(path, require_audio=True)
                valid = True
            except RuntimeError:
                logger.warning('Regenerating invalid preview %s', path.name)
        if not valid:
            await self.synthesize_speech(text, voice=voice, model=model, speed=speed, output_path=path)
        return {'voice_id': meta['id'], 'name': meta['name'], 'speed': speed,
                'preview_url': storage_service.get_relative_url(path), 'sample_text': text}

    async def get_audio_duration(self, audio_path: Path) -> float:
        from app.services.media_process import probe_media
        return await probe_media(audio_path, require_audio=True)

    @staticmethod
    def build_chained_atempo_filter(speed_factor: float) -> str:
        if not 0.5 <= speed_factor <= 2.5:
            raise ValueError('Audio speed factor must be between 0.5 and 2.5')
        filters = []
        while speed_factor > 1.25:
            filters.append('atempo=1.220')
            speed_factor /= 1.22
        filters.append(f'atempo={speed_factor:.6f}')
        return ','.join(filters)

    async def dub_project_timeline(
        self, cues_data: List[Dict[str, Any]], total_duration: float, output_audio_path: Path,
        default_voice: str = "vi-VN-HoaiMyNeural", model: str = "tts-1", default_speed: float = 1.,
        speaker_voice_map: Optional[Dict[str, str]] = None, progress_callback=None,
        speaker_speed_map: Optional[Dict[str, float]] = None,
    ) -> Path:
        import hashlib
        import json
        import math
        import tempfile
        from app.services.pcm_mixer import mix_pcm_blocks
        from app.services.media_process import run_media, probe_media, validate_duration
        from app.services.asr_service import ASRService
        if not cues_data or not math.isfinite(total_duration) or total_duration <= 0:
            raise ValueError('Dubbing requires subtitle cues and a valid media duration')
        sorted_cues = sorted(cues_data, key=lambda c: c['start_time'])
        output_audio_path.parent.mkdir(parents=True, exist_ok=True)
        # Speech content cache is independent of job/output versions. The caller's
        # project directory is the stable namespace; tempo includes timing.
        namespace = hashlib.sha256(str(output_audio_path.parent.resolve()).encode()).hexdigest()[:24]
        cache_dir = settings.TEMP_SCRATCH_DIR / 'speech' / namespace
        cache_dir.mkdir(parents=True, exist_ok=True)
        workers = min(settings.TTS_MAX_CONCURRENCY, len(sorted_cues))
        semaphore, progress_lock = asyncio.Semaphore(workers), asyncio.Lock()
        measurements = [None] * len(sorted_cues)
        overlaps = []
        preceding_end = 0.
        for index, cue in enumerate(sorted_cues):
            overlaps.append(float(cue['start_time']) < preceding_end or (
                index + 1 < len(sorted_cues) and float(sorted_cues[index + 1]['start_time']) < float(cue['end_time'])))
            preceding_end = max(preceding_end, float(cue['end_time']))
        done = 0
        with tempfile.TemporaryDirectory(prefix='mix_', dir=settings.TEMP_SCRATCH_DIR) as scratch:
            work = Path(scratch)
            async def prepare(index, cue):
                nonlocal done
                async with semaphore:
                    text = (cue.get('translated_text') or '').strip()
                    if not text:
                        raise ValueError(f"Cue {cue.get('cue_index')} has no translation")
                    start, end = float(cue['start_time']), float(cue['end_time'])
                    if not math.isfinite(start + end) or start < 0 or end <= start or end > total_duration + 0.1:
                        raise ValueError('Invalid dubbing cue timing')
                    start_sample = int(round(start * 24000))
                    window_samples = int(math.floor(min(end, total_duration) * 24000)) - start_sample
                    if window_samples <= 0:
                        raise ValueError('Dubbing cue is shorter than one audio sample')
                    tag = cue.get('speaker_tag', 'SPEAKER_00')
                    voice = (speaker_voice_map or {}).get(tag, default_voice)
                    speed = (speaker_speed_map or {}).get(tag, default_speed)
                    key = hashlib.sha256(json.dumps(['v4', voice, model, speed, text, VOICE_PROFILES.get(voice)], ensure_ascii=False).encode()).hexdigest()
                    clip = cache_dir / f'{key}.mp3'
                    from app.services.storage_service import storage_service
                    lock_dir = cache_dir / 'locks' / key
                    lock_dir.mkdir(parents=True, exist_ok=True)
                    async with storage_service._upload_lock(lock_dir):
                        if clip.exists():
                            try:
                                actual = await probe_media(clip, require_audio=True)
                            except RuntimeError:
                                clip.unlink(missing_ok=True)
                        if not clip.exists():
                            await self.synthesize_speech(text, voice, model, speed, clip)
                    await probe_media(clip, require_audio=True)
                    pcm = work / f'{index}.pcm'
                    await run_media([settings.get_ffmpeg_bin(), '-y', '-i', str(clip), '-f', 's16le', '-ar', '24000', '-ac', '1', str(pcm)])
                    if not pcm.is_file() or pcm.stat().st_size == 0:
                        raise RuntimeError('Speech decoding produced no PCM')
                    source_pcm = pcm
                    source_samples = pcm.stat().st_size // 2
                    fitted_samples, factor = source_samples, 1.
                    # Container duration includes codec padding. Fit decoded samples,
                    # and remeasure atempo output rather than cutting the last word.
                    for attempt in range(3):
                        if fitted_samples <= window_samples:
                            break
                        required = source_samples / window_samples
                        if required > 2.5:
                            break
                        if attempt == 0:
                            factor = required
                        else:
                            factor = min(2.5, factor * fitted_samples / window_samples * 1.01)
                        pcm = work / f'{index}_fit_{attempt}.pcm'
                        await run_media([settings.get_ffmpeg_bin(), '-y', '-f', 's16le', '-ar', '24000', '-ac', '1',
                                         '-i', str(source_pcm), '-af', self.build_chained_atempo_filter(factor),
                                         '-f', 's16le', str(pcm)])
                        fitted_samples = pcm.stat().st_size // 2
                    if fitted_samples <= 0 or fitted_samples > window_samples:
                        raise RuntimeError(f'Cue {cue.get("cue_index")} cannot fit its timeline; shorten the translation or edit timing')
                    measurements[index] = {
                        'cue_index': cue.get('cue_index', index + 1), 'start_time': start, 'end_time': end,
                        'source_duration': source_samples / 24000, 'fitted_duration': fitted_samples / 24000,
                        'audio_end': (start_sample + fitted_samples) / 24000, 'speedup': factor,
                        'overlaps': overlaps[index],
                    }
                    async with progress_lock:
                        done += 1
                        if progress_callback:
                            await progress_callback(done, len(sorted_cues), False, text)
                    return start_sample, pcm
            pending_cues = iter(enumerate(sorted_cues))
            clips = [None] * len(sorted_cues)
            async def prepare_worker():
                # Advance synchronously before awaiting: each worker owns one cue
                # and long transcripts do not allocate one asyncio Task per cue.
                for index, cue in pending_cues:
                    clips[index] = await prepare(index, cue)
            tasks = [asyncio.create_task(prepare_worker()) for _ in range(workers)]
            try:
                await asyncio.gather(*tasks)
            except BaseException:
                for task in tasks:
                    task.cancel()
                await asyncio.gather(*tasks, return_exceptions=True)
                raise
            if progress_callback:
                await progress_callback(0, 1, True)
            raw = work / 'timeline.pcm'
            await ASRService._blocking(lambda: mix_pcm_blocks(clips, raw, int(round(total_duration * 24000))))
            temporary = work / 'timeline.mp3'
            await run_media([settings.get_ffmpeg_bin(), '-y', '-f', 's16le', '-ar', '24000', '-ac', '1', '-i', str(raw), '-c:a', 'libmp3lame', '-b:a', '192k', str(temporary)])
            await validate_duration(temporary, total_duration, audio=True)
            from app.schemas.tts import DubbingTimingReport
            report = DubbingTimingReport(cue_count=len(measurements), overlap_cue_count=sum(overlaps),
                                         max_speedup=max(item['speedup'] for item in measurements), cues=measurements)
            report_file = work / 'timing.json'
            report_file.write_text(report.model_dump_json(), encoding='utf-8')
            report_file.replace(output_audio_path.with_suffix('.timing.json'))
            temporary.replace(output_audio_path)
            if progress_callback:
                await progress_callback(1, 1, True)
        return output_audio_path

    async def mix_dubbed_video(self, video_path: Path, dubbed_audio_path: Path, output_video_path: Path,
                               ducking_volume: float = 0.18, mix_original: bool = True) -> Path:
        from app.services.media_process import run_media, probe_media, validate_duration
        duration = await probe_media(video_path, require_video=True)
        await probe_media(dubbed_audio_path, require_audio=True)
        output_video_path.parent.mkdir(parents=True, exist_ok=True)
        command = [settings.get_ffmpeg_bin(), '-y', '-i', str(video_path), '-i', str(dubbed_audio_path)]
        if mix_original:
            await probe_media(video_path, require_audio=True)
            command += ['-filter_complex', f'[0:a]volume={ducking_volume:.3f}[bg];[bg][1:a]amix=inputs=2:duration=first:normalize=0[aout]', '-map', '0:v:0', '-map', '[aout]']
        else:
            command += ['-map', '0:v:0', '-map', '1:a:0', '-af', 'apad']
        command += ['-t', str(duration), '-c:v', 'copy', '-c:a', 'aac', '-b:a', '192k', str(output_video_path)]
        await run_media(command)
        await validate_duration(output_video_path, duration, video=True, audio=True)
        return output_video_path


tts_service = TTSService()
