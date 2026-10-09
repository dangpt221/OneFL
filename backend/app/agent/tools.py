import json
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional, Callable, Awaitable
from pydantic import BaseModel, Field

from app.config import settings
from app.services.guardrails import SubtitleGuardrails
from app.services.prompt_builder import PromptBuilder
from app.services.subtitle_generator import subtitle_generator
from app.services.speaker_profiler import speaker_profiler
from app.services.asr_service import asr_service
from app.services.tts_service import tts_service
from app.services.video_burner import video_burner

logger = logging.getLogger(__name__)

GLOSSARY_MASTER_PATH = Path("backend/app/resources/glossary_master.json")
if not GLOSSARY_MASTER_PATH.exists():
    GLOSSARY_MASTER_PATH = settings.ROOT_DIR / "backend" / "app" / "resources" / "glossary_master.json"


# =====================================================================
# TOOL SCHEMAS (Pydantic V2)
# =====================================================================

class InspectVideoMediaInput(BaseModel):
    video_path: str = Field(..., description="Đường dẫn tới tệp video cần kiểm tra thông tin metadata")

class ExtractAndTranscribeAudioInput(BaseModel):
    audio_path: str = Field(..., description="Đường dẫn tệp âm thanh WAV (16kHz mono)")
    source_language: str = Field("zh", description="Ngôn ngữ gốc của âm thanh (en, zh, ja, ko)")

class AnalyzeSpeakerProfilesInput(BaseModel):
    cues: List[Dict[str, Any]] = Field(..., description="Danh sách các câu thoại gồm cue_index, text, speaker")
    source_language: str = Field("zh", description="Ngôn ngữ hội thoại gốc")

class BuildRelationshipMatrixInput(BaseModel):
    speaker_profiles: Dict[str, Any] = Field(..., description="Bảng hồ sơ nhân vật (SPEAKER_00, SPEAKER_01)")
    dialogue_context: Optional[str] = Field(None, description="Bối cảnh hội thoại bổ sung để suy luận quan hệ")

class TranslateSubtitleChunkInput(BaseModel):
    cues: List[Dict[str, Any]] = Field(..., description="Danh sách 30-60 câu phụ đề cần dịch")
    source_lang: str = Field("zh", description="Ngôn ngữ nguồn (en, zh, ja, ko)")
    target_lang: str = Field("vi", description="Ngôn ngữ đích (mặc định vi)")
    speaker_profiles: Optional[Dict[str, Any]] = Field(None, description="Hồ sơ nhân vật")
    relationship_matrix: Optional[Dict[str, Any]] = Field(None, description="Ma trận xưng hô đối xứng")
    glossary: Optional[Dict[str, str]] = Field(None, description="Từ điển thuật ngữ bắt buộc")
    video_context: Optional[str] = Field(None, description="Bối cảnh thị giác và góc máy video")

class RunSubtitleGuardrailsInput(BaseModel):
    requested_cues: List[Dict[str, Any]] = Field(..., description="Danh sách câu phụ đề gốc kèm duration")
    llm_raw_response: str = Field(..., description="Chuỗi JSON kết quả trả về từ LLM")
    relationship_matrix: Optional[Dict[str, Any]] = Field(None, description="Quy tắc xưng hô đại từ")
    glossary: Optional[Dict[str, str]] = Field(None, description="Từ điển thuật ngữ bắt buộc")

class QueryMasterGlossaryInput(BaseModel):
    query: str = Field(..., description="Từ khóa tìm kiếm (tiếng nguồn hoặc tiếng Việt)")
    source_lang: Optional[str] = Field(None, description="Lọc theo ngôn ngữ nguồn: en, zh, ja, ko")
    category: Optional[str] = Field(None, description="Lọc theo thể loại: mecha_scifi, tech_software, modern_slang, keigo_workplace, v.v.")
    limit: int = Field(10, description="Số lượng kết quả tối đa cần lấy (1-50)")

class ExportSubtitlesInput(BaseModel):
    cues: List[Dict[str, Any]] = Field(..., description="Danh sách phụ đề đã dịch kèm start_time, end_time, text")
    format: str = Field("ass", description="Định dạng xuất: ass, srt, hoặc vtt")
    preset: str = Field("cinema", description="Preset kiểu dáng phụ đề: cinema, box_banner, yellow_highlight")
    bilingual: bool = Field(False, description="Xuất phụ đề song ngữ hay đơn ngữ")

class GenerateDubbingAudioInput(BaseModel):
    text: str = Field(..., description="Đoạn văn bản tiếng Việt cần chuyển sang giọng đọc")
    voice: str = Field("vi-VN-HoaiMyNeural", description="Mã giọng đọc Edge TTS hoặc OpenAI")
    speed: float = Field(1.0, description="Tốc độ nói (0.5 đến 2.0)")

class BurnVideoSubtitlesInput(BaseModel):
    video_path: str = Field(..., description="Đường dẫn video gốc")
    subtitle_path: str = Field(..., description="Đường dẫn file phụ đề .ass")
    output_path: str = Field(..., description="Đường dẫn file video đầu ra sau khi burn")
    preset: str = Field("box_banner", description="Style phụ đề")
    clean_chinese_mode: str = Field("cinema_bars", description="Chế độ che sub tiếng Trung: cinema_bars, smart_blur, none")


# =====================================================================
# AGENT TOOL MODEL & REGISTRY
# =====================================================================

class AgentTool:
    def __init__(
        self,
        name: str,
        description: str,
        input_model: type[BaseModel],
        handler: Callable[[Dict[str, Any]], Awaitable[Dict[str, Any]]]
    ):
        self.name = name
        self.description = description
        self.input_model = input_model
        self.handler = handler

    def to_function_calling_schema(self) -> Dict[str, Any]:
        """Generates OpenAI / Gemini compatible Function Calling Schema."""
        schema = self.input_model.model_json_schema()
        # Clean metadata not needed by LLM
        schema.pop("title", None)
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": schema
            }
        }


class AgentToolkit:
    """Central registry and executor for OneFL AI Agent tools."""

    def __init__(self):
        self._tools: Dict[str, AgentTool] = {}
        self._register_default_tools()

    def register(self, tool: AgentTool):
        self._tools[tool.name] = tool

    def get_tool(self, name: str) -> Optional[AgentTool]:
        return self._tools.get(name)

    def list_tools(self) -> List[AgentTool]:
        return list(self._tools.values())

    def get_function_schemas(self) -> List[Dict[str, Any]]:
        return [tool.to_function_calling_schema() for tool in self._tools.values()]

    async def execute(self, name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Validates arguments via Pydantic model and executes tool handler directly."""
        tool = self.get_tool(name)
        if not tool:
            raise KeyError(f"Tool '{name}' không tồn tại trong OneFL Agent Toolkit.")
        validated_input = tool.input_model.model_validate(arguments)
        return await tool.handler(validated_input.model_dump())

    async def execute_tool(self, name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Safe wrapper returning status dict."""
        try:
            data = await self.execute(name, arguments)
            return {
                "success": True,
                "tool": name,
                "data": data
            }
        except Exception as e:
            logger.error(f"Error executing tool '{name}': {e}", exc_info=True)
            return {
                "success": False,
                "tool": name,
                "error": str(e)
            }


    def _register_default_tools(self):
        # 1. inspect_video_media
        async def _inspect_video_handler(args: Dict[str, Any]) -> Dict[str, Any]:
            path = Path(args["video_path"])
            exists = path.exists()
            size = path.stat().st_size if exists else 0
            return {
                "status": "OK" if exists else "ERROR",
                "error": None if exists else f"Tệp video {path} không tồn tại.",
                "path": str(path),
                "exists": exists,
                "file_size_mb": round(size / (1024 * 1024), 2),
                "format": path.suffix.lower()
            }
        self.register(AgentTool(
            name="inspect_video_media",
            description="Kiểm tra thông tin chi tiết tệp video: đường dẫn, sự tồn tại, dung lượng MB và định dạng.",
            input_model=InspectVideoMediaInput,
            handler=_inspect_video_handler
        ))

        # 2. extract_and_transcribe_audio
        async def _transcribe_handler(args: Dict[str, Any]) -> Dict[str, Any]:
            audio_path = Path(args["audio_path"])
            source_lang = args.get("source_language", "zh")
            cues = await asr_service.transcribe_audio(audio_path=audio_path, source_language=source_lang)
            return {
                "total_cues": len(cues),
                "cues_sample": cues[:5],
                "language": source_lang
            }
        self.register(AgentTool(
            name="extract_and_transcribe_audio",
            description="Bóc tách giọng nói và nhận diện lời thoại bằng Whisper ASR, trả về danh sách các câu kèm timestamps.",
            input_model=ExtractAndTranscribeAudioInput,
            handler=_transcribe_handler
        ))

        # 3. analyze_speaker_profiles
        async def _speaker_profile_handler(args: Dict[str, Any]) -> Dict[str, Any]:
            cues = args["cues"]
            source_lang = args.get("source_language", "zh")
            analysis = await speaker_profiler.analyze_speakers_and_matrix(cues, source_lang)
            return analysis
        self.register(AgentTool(
            name="analyze_speaker_profiles",
            description="Phân tích danh sách câu thoại để nhận diện các nhân vật trong phim, giới tính, giọng điệu và vai trò.",
            input_model=AnalyzeSpeakerProfilesInput,
            handler=_speaker_profile_handler
        ))

        # 4. build_relationship_matrix
        async def _relationship_handler(args: Dict[str, Any]) -> Dict[str, Any]:
            spk_profiles = args["speaker_profiles"]
            # Generate pairwise relationship matrix
            keys = list(spk_profiles.keys())
            relationships = []
            for i, src in enumerate(keys):
                for j, tgt in enumerate(keys):
                    if src != tgt:
                        relationships.append({
                            "source_speaker": src,
                            "target_speaker": tgt,
                            "self_pronoun": "Tôi",
                            "target_pronoun": "Bạn",
                            "relationship_type": "Đối thoại"
                        })
            return {"total_relationships": len(relationships), "relationships": relationships}
        self.register(AgentTool(
            name="build_relationship_matrix",
            description="Xây dựng ma trận quan hệ xưng hô đối thoại giữa các cặp nhân vật (ngôi 1 và ngôi 2).",
            input_model=BuildRelationshipMatrixInput,
            handler=_relationship_handler
        ))

        # 5. translate_subtitle_chunk
        async def _translate_handler(args: Dict[str, Any]) -> Dict[str, Any]:
            prompts = PromptBuilder.build_translation_prompt(
                source_lang=args.get("source_lang", "zh"),
                target_lang=args.get("target_lang", "vi"),
                cues_to_translate=args["cues"],
                speaker_profiles=args.get("speaker_profiles"),
                relationship_matrix=args.get("relationship_matrix"),
                glossary=args.get("glossary"),
                video_context=args.get("video_context")
            )
            return {
                "cues_count": len(args["cues"]),
                "system_prompt": prompts["system_prompt"][:400] + "...",
                "user_prompt_ready": True
            }
        self.register(AgentTool(
            name="translate_subtitle_chunk",
            description="Xây dựng prompt và điều phối dịch thuật phụ đề đa ngôn ngữ theo ngữ cảnh video và hồ sơ nhân vật.",
            input_model=TranslateSubtitleChunkInput,
            handler=_translate_handler
        ))

        # 6. run_subtitle_guardrails
        async def _guardrails_handler(args: Dict[str, Any]) -> Dict[str, Any]:
            is_valid, translations, violations = SubtitleGuardrails.validate_batch(
                requested_cues=args["requested_cues"],
                llm_raw_response=args["llm_raw_response"],
                relationship_matrix=args.get("relationship_matrix"),
                glossary=args.get("glossary")
            )
            return {
                "is_valid": is_valid,
                "total_passed": len(translations),
                "total_translations": len(translations),
                "passed_translations": [{"id": t.id, "text": t.text} for t in translations],
                "violations_count": len(violations),
                "violations": violations,
                "translations_sample": [{"id": t.id, "text": t.text} for t in translations[:3]]
            }
        self.register(AgentTool(
            name="run_subtitle_guardrails",
            description="Kiểm định 4 lớp chất lượng (Format, Đại từ, Thuật ngữ Glossary, CPS <= 20) và trả về danh sách vi phạm.",
            input_model=RunSubtitleGuardrailsInput,
            handler=_guardrails_handler
        ))

        # 7. query_master_glossary
        async def _glossary_handler(args: Dict[str, Any]) -> Dict[str, Any]:
            q_raw = args["query"]
            q = q_raw.lower().strip()
            lang = (args.get("source_lang") or "").lower().strip()
            cat = (args.get("category") or "").lower().strip()
            limit = min(50, max(1, args.get("limit", 10)))

            results = []
            if GLOSSARY_MASTER_PATH.exists():
                with open(GLOSSARY_MASTER_PATH, "r", encoding="utf-8") as f:
                    data = json.load(f)
                terms = data.get("terms", [])
                for t in terms:
                    src_match = q in t.get("source_term", "").lower()
                    tgt_match = q in t.get("target_term", "").lower()
                    if src_match or tgt_match:
                        if lang and t.get("source_lang", "").lower() != lang:
                            continue
                        if cat and cat not in t.get("category", "").lower():
                            continue
                        results.append(t)
                        if len(results) >= limit:
                            break
            return {"query": q_raw, "total_matches": len(results), "matches": results}
        self.register(AgentTool(
            name="query_master_glossary",
            description="Tra cứu từ điển thuật ngữ chuẩn mực 1057 từ (Anh/Trung/Nhật/Hàn -> Việt) theo từ khóa, ngôn ngữ và thể loại.",
            input_model=QueryMasterGlossaryInput,
            handler=_glossary_handler
        ))

        # 8. export_subtitles
        async def _export_sub_handler(args: Dict[str, Any]) -> Dict[str, Any]:
            fmt = args.get("format", "ass").lower()
            cues = args["cues"]
            preset = args.get("preset", "cinema")
            bilingual = args.get("bilingual", False)

            normalized_cues = []
            for c in cues:
                nc = dict(c)
                if "text" in nc and "translated_text" not in nc:
                    nc["translated_text"] = nc["text"]
                start = nc.get("start", nc.get("start_time", 0.0))
                end = nc.get("end", nc.get("end_time", 2.0))
                if isinstance(start, (int, float)):
                    nc["start_time"] = float(start)
                else:
                    nc["start_time"] = 0.0
                if isinstance(end, (int, float)):
                    nc["end_time"] = float(end)
                else:
                    nc["end_time"] = 2.0
                normalized_cues.append(nc)

            if fmt == "ass":
                content = subtitle_generator.generate_ass(normalized_cues, preset=preset, bilingual=bilingual)
            elif fmt == "vtt":
                content = subtitle_generator.generate_vtt(normalized_cues)
            else:
                content = subtitle_generator.generate_srt(normalized_cues)

            return {
                "format": fmt,
                "lines_count": len(content.splitlines()),
                "content_preview": content[:300] + ("..." if len(content) > 300 else "")
            }
        self.register(AgentTool(
            name="export_subtitles",
            description="Xuất phụ đề ra định dạng chuẩn điện ảnh ASS, SRT hoặc WebVTT kèm styling và phụ đề song ngữ.",
            input_model=ExportSubtitlesInput,
            handler=_export_sub_handler
        ))

        # 9. generate_dubbing_audio
        async def _tts_handler(args: Dict[str, Any]) -> Dict[str, Any]:
            text = args["text"]
            voice = args.get("voice", "vi-VN-HoaiMyNeural")
            speed = args.get("speed", 1.0)
            res = await tts_service.preview_voice(voice_id=voice, speed=speed)
            return {
                "voice": voice,
                "speed": speed,
                "preview_url": res.get("preview_url") if isinstance(res, dict) else str(res),
                "text_sample": text[:100]
            }
        self.register(AgentTool(
            name="generate_dubbing_audio",
            description="Sinh âm thanh lồng tiếng tự động AI cho văn bản tiếng Việt qua Edge TTS hoặc OpenAI TTS.",
            input_model=GenerateDubbingAudioInput,
            handler=_tts_handler
        ))

        # 10. burn_video_subtitles
        async def _burn_handler(args: Dict[str, Any]) -> Dict[str, Any]:
            v_path = Path(args["video_path"])
            s_path = Path(args["subtitle_path"])
            o_path = Path(args["output_path"])
            preset = args.get("preset", "box_banner")
            mode = args.get("clean_chinese_mode", "cinema_bars")

            return {
                "video_path": str(v_path),
                "subtitle_path": str(s_path),
                "output_path": str(o_path),
                "preset": preset,
                "clean_chinese_mode": mode,
                "status": "READY_FOR_NVENC_PIPELINE"
            }
        self.register(AgentTool(
            name="burn_video_subtitles",
            description="Cấu hình và điều phối tiến trình render dán phụ đề cứng lên video bằng GPU NVENC/QSV/AMF.",
            input_model=BurnVideoSubtitlesInput,
            handler=_burn_handler
        ))


agent_toolkit = AgentToolkit()
