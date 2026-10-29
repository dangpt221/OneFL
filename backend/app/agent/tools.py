import json
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional, Callable, Awaitable, Literal
from pydantic import BaseModel, Field
from app.agent.contracts import ToolInput, ToolOutcome, QueuedOutcome, JobOutcome, normalize_cues

from app.config import settings
from app.services.guardrails import SubtitleGuardrails
from app.services.speaker_profiler import speaker_profiler
from app.services.tts_service import tts_service

logger = logging.getLogger(__name__)

GLOSSARY_MASTER_PATH = Path(__file__).resolve().parents[1] / "resources" / "glossary_master.json"


# =====================================================================
# TOOL SCHEMAS (Pydantic V2)
# =====================================================================

class InspectVideoMediaInput(ToolInput):
    video_path: str = Field(..., description="Đường dẫn tới tệp video cần kiểm tra thông tin metadata")

class ExtractAndTranscribeAudioInput(ToolInput):
    project_id: Optional[str] = Field(None, min_length=1, max_length=36)
    audio_path: Optional[str] = None
    video_path: Optional[str] = None
    force_reprocess: bool = False
    source_language: Optional[str] = Field(None, description="Ngôn ngữ nguồn; mặc định theo project")

class AnalyzeSpeakerProfilesInput(ToolInput):
    cues: List[Dict[str, Any]] = Field(..., min_length=1, max_length=300, description="Danh sách các câu thoại gồm cue_index, text, speaker")
    source_language: str = Field("zh", description="Ngôn ngữ hội thoại gốc")

class BuildRelationshipMatrixInput(ToolInput):
    speaker_profiles: Dict[str, Any] = Field(..., description="Bảng hồ sơ nhân vật (SPEAKER_00, SPEAKER_01)")
    dialogue_context: Optional[str] = Field(None, description="Bối cảnh hội thoại bổ sung để suy luận quan hệ")

class TranslateSubtitleChunkInput(ToolInput):
    cues: List[Dict[str, Any]] = Field(..., min_length=1, max_length=60, description="Danh sách tối đa 60 câu phụ đề cần dịch")
    source_lang: str = Field("zh", description="Ngôn ngữ nguồn (en, zh, ja, ko)")
    target_lang: str = Field("vi", description="Ngôn ngữ đích (mặc định vi)")
    speaker_profiles: Optional[Dict[str, Any]] = Field(None, description="Hồ sơ nhân vật")
    relationship_matrix: Optional[Dict[str, Any] | List[Dict[str, Any]]] = Field(None, description="Ma trận xưng hô")
    glossary: Optional[Dict[str, str]] = Field(None, description="Từ điển thuật ngữ bắt buộc")
    video_context: Optional[str] = Field(None, description="Bối cảnh thị giác và góc máy video")
    video_path: Optional[str] = None

class RunSubtitleGuardrailsInput(ToolInput):
    requested_cues: List[Dict[str, Any]] = Field(..., min_length=1, max_length=300, description="Danh sách câu phụ đề gốc kèm duration")
    llm_raw_response: str = Field(..., description="Chuỗi JSON kết quả trả về từ LLM")
    relationship_matrix: Optional[Dict[str, Any] | List[Dict[str, Any]]] = Field(None, description="Quy tắc xưng hô đại từ")
    glossary: Optional[Dict[str, str]] = Field(None, description="Từ điển thuật ngữ bắt buộc")

class QueryMasterGlossaryInput(ToolInput):
    query: str = Field(..., description="Từ khóa tìm kiếm (tiếng nguồn hoặc tiếng Việt)")
    source_lang: Optional[str] = Field(None, description="Lọc theo ngôn ngữ nguồn: en, zh, ja, ko")
    category: Optional[str] = Field(None, description="Lọc theo thể loại: mecha_scifi, tech_software, modern_slang, keigo_workplace, v.v.")
    limit: int = Field(10, ge=1, le=50, description="Số lượng kết quả tối đa cần lấy (1-50)")

class ExportSubtitlesInput(ToolInput):
    project_id: Optional[str] = Field(None, min_length=1, max_length=36)
    cues: Optional[List[Dict[str, Any]]] = Field(None, max_length=500, description="Bỏ trống để xuất cue từ project")
    format: Literal['ass', 'srt', 'vtt'] = Field("ass", description="Định dạng xuất: ass, srt, hoặc vtt")
    preset: Literal['cinema', 'box_banner', 'yellow_highlight'] = 'cinema'
    bilingual: bool = Field(False, description="Xuất phụ đề song ngữ hay đơn ngữ")

class GenerateDubbingAudioInput(ToolInput):
    text: str = Field(..., min_length=1, max_length=1000, description="Đoạn văn bản để nghe thử; dùng dub_project_video cho project")
    voice: str = Field("vi-VN-HoaiMyNeural", description="Mã giọng đọc Edge TTS hoặc OpenAI")
    speed: float = Field(1.0, ge=0.5, le=2.0)
    model: Optional[str] = Field(None, min_length=1, max_length=100)

class BurnVideoSubtitlesInput(ToolInput):
    project_id: Optional[str] = Field(None, min_length=1, max_length=36)
    video_path: Optional[str] = None
    subtitle_path: Optional[str] = None
    output_path: Optional[str] = None
    clean_chinese_mode: Literal['cinema_bars', 'bottom_bar', 'smart_blur', 'cinema_zoom', 'none'] = 'cinema_bars'


# =====================================================================
# AGENT TOOL MODEL & REGISTRY
# =====================================================================

class AgentTool:
    def __init__(
        self,
        name: str,
        description: str,
        input_model: type[BaseModel],
        handler: Callable[[Dict[str, Any]], Awaitable[Dict[str, Any]]],
        output_model: type[ToolOutcome] = ToolOutcome,
    ):
        self.name = name
        self.description = description
        self.input_model = input_model
        self.handler = handler
        self.output_model = output_model

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
        if len(json.dumps(arguments, allow_nan=False)) > 256000:
            raise ValueError('Tool input exceeds 256000 characters; use project IDs and pagination')
        from app.services.private_media import authorize_media_path
        for key in ('video_path', 'audio_path', 'subtitle_path', 'output_path'):
            path = getattr(validated_input, key, None)
            if path:
                if name == 'inspect_video_media' and not Path(path).is_file():
                    raise FileNotFoundError('Video file does not exist')
                await authorize_media_path(Path(path))
        result = await tool.handler(validated_input.model_dump())
        return tool.output_model.model_validate(result).model_dump()

    async def execute_tool(self, name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Safe wrapper returning status dict."""
        try:
            data = await self.execute(name, arguments)
            return {
                "success": data.get('success', True),
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
            from app.services.media_process import probe_media
            path = Path(args["video_path"])
            exists = path.exists()
            size = path.stat().st_size if exists else 0
            return {
                "status": "OK" if exists else "ERROR",
                "error": None if exists else f"Tệp video {path} không tồn tại.",
                "path": str(path),
                "exists": exists,
                "file_size_mb": round(size / (1024 * 1024), 2),
                "format": path.suffix.lower(),
                "duration_seconds": await probe_media(path, require_video=True)
            }
        self.register(AgentTool(
            name="inspect_video_media",
            description="Kiểm tra thông tin chi tiết tệp video: đường dẫn, sự tồn tại, dung lượng MB và định dạng.",
            input_model=InspectVideoMediaInput,
            handler=_inspect_video_handler
        ))

        # 2. extract_and_transcribe_audio
        async def _transcribe_handler(args: Dict[str, Any]) -> Dict[str, Any]:
            from app.services.agent_project_service import submit_media_tool
            return await submit_media_tool('TRANSCRIBE', args)
        self.register(AgentTool(
            name="extract_and_transcribe_audio",
            description="Xếp job trích xuất audio và ASR cho project; trả job_id. Đọc kết quả bằng get_job_status/get_project_context.",
            input_model=ExtractAndTranscribeAudioInput,
            handler=_transcribe_handler,
            output_model=QueuedOutcome,
        ))

        # 3. analyze_speaker_profiles
        async def _speaker_profile_handler(args: Dict[str, Any]) -> Dict[str, Any]:
            cues = [{**c, 'speaker': c['speaker_tag'], 'text': c['original_text']} for c in normalize_cues(args['cues'])]
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
            from app.services.llm_router import llm_router
            from app.schemas.speaker import RelationshipMatrixCreate
            profiles = args['speaker_profiles']
            raw = await llm_router.generate_completion(
                'Infer only relationships supported by the supplied profiles and dialogue. Return JSON {"relationships": [{"source_speaker":"...", "target_speaker":"...", "self_pronoun":"...", "target_pronoun":"...", "relationship_type":"...", "honorific_notes":"evidence or uncertainty"}]}. Use Vietnamese pronouns. Return an empty list if there is insufficient evidence.',
                json.dumps({'speakers': profiles, 'dialogue_context': args.get('dialogue_context')}, ensure_ascii=False), temperature=0.2)
            values = json.loads(SubtitleGuardrails.clean_json_response(raw))['relationships']
            relationships, seen = [], set()
            for item in values:
                relationship = RelationshipMatrixCreate.model_validate(item).model_dump()
                pair = (relationship['source_speaker'], relationship['target_speaker'])
                if pair[0] not in profiles or pair[1] not in profiles or pair[0] == pair[1] or pair in seen:
                    raise ValueError('Invalid or duplicate relationship speaker pair')
                seen.add(pair)
                relationships.append(relationship)
            return {'total_relationships': len(relationships), 'relationships': relationships}
        self.register(AgentTool(
            name="build_relationship_matrix",
            description="Xây dựng ma trận quan hệ xưng hô đối thoại giữa các cặp nhân vật (ngôi 1 và ngôi 2).",
            input_model=BuildRelationshipMatrixInput,
            handler=_relationship_handler
        ))

        # 5. translate_subtitle_chunk
        async def _translate_handler(args: Dict[str, Any]) -> Dict[str, Any]:
            from app.services.translation_service import translation_service
            cues = normalize_cues(args['cues'])
            translations = await translation_service.translate_project_cues(
                'agent', cues, source_lang=args['source_lang'], target_lang=args['target_lang'],
                speaker_profiles=args.get('speaker_profiles'), relationship_matrix=args.get('relationship_matrix'),
                glossary=args.get('glossary'), video_context=args.get('video_context'),
                video_path=args.get('video_path'))
            return {'cues_count': len(cues), 'translations': translations}
        self.register(AgentTool(
            name="translate_subtitle_chunk",
            description="Xây dựng prompt và điều phối dịch thuật phụ đề đa ngôn ngữ theo ngữ cảnh video và hồ sơ nhân vật.",
            input_model=TranslateSubtitleChunkInput,
            handler=_translate_handler
        ))

        # 6. run_subtitle_guardrails
        async def _guardrails_handler(args: Dict[str, Any]) -> Dict[str, Any]:
            cues = normalize_cues(args['requested_cues'])
            is_valid, translations, violations = SubtitleGuardrails.validate_batch(
                requested_cues=[{**c, 'id': c['cue_index'], 'text': c['original_text'],
                                 'speaker': c['speaker_tag'], 'duration': c['end_time'] - c['start_time']} for c in cues],
                llm_raw_response=args["llm_raw_response"],
                relationship_matrix=args.get("relationship_matrix"),
                glossary=args.get("glossary")
            )
            rejected = {v.get('cue_id') for v in violations}
            accepted = [t for t in translations if t.id not in rejected] if all('cue_id' in v for v in violations) else []
            return {
                "success": is_valid,
                "is_valid": is_valid,
                "total_passed": len(accepted),
                "total_translations": len(translations),
                "passed_translations": [{"id": t.id, "text": t.text} for t in accepted],
                "rejected_ids": sorted(t.id for t in translations if t not in accepted),
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
            description="Tra cứu từ điển thuật ngữ chuẩn mực 290 từ (Anh/Trung/Nhật/Hàn -> Việt) theo từ khóa, ngôn ngữ và thể loại.",
            input_model=QueryMasterGlossaryInput,
            handler=_glossary_handler
        ))

        # 8. export_subtitles
        async def _export_sub_handler(args: Dict[str, Any]) -> Dict[str, Any]:
            if args.get('project_id'):
                from app.services.agent_project_service import export_project
                return await export_project(args)
            fmt = args.get("format", "ass").lower()
            if not args.get('cues'):
                raise ValueError('Provide cues or project_id')
            cues = normalize_cues([{**c, 'translated_text': c.get('translated_text') or c.get('text')} for c in args['cues']])
            preset = args.get("preset", "cinema")
            bilingual = args.get("bilingual", False)

            from app.services.agent_project_service import subtitle_content
            content = subtitle_content(cues, fmt, preset, bilingual)

            return {
                "format": fmt,
                "lines_count": len(content.splitlines()),
                "content": content,
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
            res = await tts_service.generate_preview(voice=voice, speed=speed, custom_text=text, model=args.get('model'))
            return {
                "voice": voice,
                "speed": speed,
                "preview_url": res.get("preview_url") if isinstance(res, dict) else str(res),
                "text_sample": text[:100]
            }
        self.register(AgentTool(
            name="generate_dubbing_audio",
            description="Nghe thử TTS cho tối đa 1000 ký tự với voice/model/speed; dùng dub_project_video để lồng tiếng theo timeline project.",
            input_model=GenerateDubbingAudioInput,
            handler=_tts_handler
        ))

        # 10. burn_video_subtitles
        async def _burn_handler(args: Dict[str, Any]) -> Dict[str, Any]:
            from app.services.agent_project_service import submit_media_tool
            return await submit_media_tool('BURN_FILE', args)
        self.register(AgentTool(
            name="burn_video_subtitles",
            description="Xếp job burn file ASS vào video project; trả job_id. Chọn preset khi export ASS, không truyền preset cho burn.",
            input_model=BurnVideoSubtitlesInput,
            handler=_burn_handler,
            output_model=QueuedOutcome,
        ))


def register_project_tools(toolkit: AgentToolkit) -> None:
    from app.agent.contracts import ProjectInput, ProjectContextInput, ProjectPipelineInput, JobInput, WaitJobInput
    from app.services.agent_project_service import project_context, start_pipeline, start_dubbing, job_status, wait_job, cancel_project
    from app.agent.contracts import ProjectDubInput

    for name, description, model, handler in (
        ('get_project_context', 'Đọc trạng thái và cue phân trang của project thuộc người dùng; không tải toàn transcript vào prompt.', ProjectContextInput, project_context),
        ('start_project_pipeline', 'Xếp pipeline project vào durable queue; trả job_id, không báo hoàn thành ngay.', ProjectPipelineInput, start_pipeline),
        ('dub_project_video', 'Xếp lồng tiếng theo timeline và mux video project, lưu cấu hình và output để Studio đồng bộ.', ProjectDubInput, start_dubbing),
        ('get_job_status', 'Đọc job/result/artifact của đúng project; QUEUED/RUNNING chưa hoàn thành.', JobInput, job_status),
        ('wait_for_job', 'Chờ tối đa 30 giây rồi trả trạng thái hiện tại; gọi lại nếu job còn pending.', WaitJobInput, wait_job),
        ('cancel_project_job', 'Yêu cầu dừng job project, chờ worker xác nhận và trả trạng thái.', ProjectInput, cancel_project),
    ):
        output = QueuedOutcome if name in {'start_project_pipeline', 'dub_project_video'} else JobOutcome if name in {'get_job_status', 'wait_for_job'} else ToolOutcome
        toolkit.register(AgentTool(name, description, model, handler, output_model=output))


agent_toolkit = AgentToolkit()
register_project_tools(agent_toolkit)
