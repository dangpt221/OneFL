import logging
import asyncio
from pathlib import Path
from typing import Optional, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete, func

from app.models.project import Project, VideoChunk
from app.models.subtitle import SubtitleCue
from app.models.speaker import SpeakerProfile, RelationshipMatrix
from app.models.glossary import GlossaryTerm
from app.services.storage_service import storage_service
from app.services.audio_service import audio_service
from app.services.asr_service import asr_service
from app.services.speaker_profiler import speaker_profiler
from app.services.translation_service import translation_service
from app.services.subtitle_generator import subtitle_generator
from app.services.video_burner import video_burner
from app.services.ws_manager import ws_manager

logger = logging.getLogger(__name__)


class WorkflowEngine:
    """Orchestrates the multi-stage video translation and burning pipeline."""

    @classmethod
    async def run_pipeline(
        cls,
        db: AsyncSession,
        project_id: str,
        start_stage: Optional[str] = None
    ):
        """Executes pipeline asynchronously with status updates and error handling."""
        # Fetch project
        result = await db.execute(select(Project).where(Project.id == project_id))
        project = result.scalar_one_or_none()
        if not project:
            logger.error(f"Project {project_id} not found.")
            return

        try:
            # GIAI ĐOẠN 1: INGESTING (Audio Extraction & VAD Chunking)
            if not start_stage or start_stage == "INGESTING":
                project.status = "PROCESSING"
                project.current_stage = "INGESTING"
                project.progress_percentage = 10
                project.error_message = "Đang trích xuất luồng âm thanh 16kHz mono từ video gốc..."
                await db.commit()
                await ws_manager.broadcast_to_project(project_id, "STAGE_CHANGED", {
                    "stage": "INGESTING",
                    "progress": 10,
                    "message": "Đang trích xuất luồng âm thanh 16kHz mono từ video gốc..."
                })

                video_path = Path(project.local_video_path) if project.local_video_path else None
                if video_path and video_path.exists():
                    p_dir = storage_service.get_project_dir(project_id)
                    audio_path = p_dir / "extracted_audio.wav"
                    if not audio_path.exists() or audio_path.stat().st_size < 1000:
                        await audio_service.extract_audio_16k_mono(video_path, audio_path)
                    project.extracted_audio_path = str(audio_path)
                    await db.commit()

            # GIAI ĐOẠN 2: ASR PROCESSING (Speech Recognition & Alignment)
            if not start_stage or start_stage in ["INGESTING", "ASR_PROCESSING"]:
                cues_exist_res = await db.execute(select(func.count(SubtitleCue.id)).where(SubtitleCue.project_id == project_id))
                existing_cues_count = cues_exist_res.scalar() or 0

                if existing_cues_count > 0 and start_stage != "ASR_PROCESSING":
                    logger.info(f"Project {project_id} already has {existing_cues_count} cues extracted. Skipping re-ASR.")
                else:
                    project.current_stage = "ASR_PROCESSING"
                    project.progress_percentage = 25
                    project.error_message = "Bắt đầu nhận diện giọng nói và bóc tách câu thoại (Whisper AI)..."
                    await db.commit()
                    await ws_manager.broadcast_to_project(project_id, "STAGE_CHANGED", {
                        "stage": "ASR_PROCESSING",
                        "progress": 25,
                        "message": "Bắt đầu nhận diện giọng nói và bóc tách câu thoại (Whisper AI)..."
                    })

                    audio_path = Path(project.extracted_audio_path) if project.extracted_audio_path else None

                    async def on_asr_progress(pct: int, msg: str):
                        project.progress_percentage = 25 + int(pct * 0.15)
                        project.error_message = msg
                        await db.commit()
                        await ws_manager.broadcast_to_project(project_id, "PROGRESS_UPDATE", {
                            "progress": 25 + int(pct * 0.15),
                            "percentage": 25 + int(pct * 0.15),
                            "message": msg
                        })

                    raw_cues = await asr_service.transcribe_audio(
                        audio_path=audio_path or Path("audio.wav"),
                        source_language=project.source_language,
                        progress_callback=on_asr_progress
                    )

                    # Clear old cues if re-running
                    await db.execute(delete(SubtitleCue).where(SubtitleCue.project_id == project_id))
                    for cue in raw_cues:
                        db_cue = SubtitleCue(
                            project_id=project_id,
                            cue_index=cue["cue_index"],
                            start_time=cue["start_time"],
                            end_time=cue["end_time"],
                            original_text=cue["original_text"],
                            speaker_tag=cue.get("speaker_tag", "SPEAKER_00")
                        )
                        db.add(db_cue)
                    
                    # Update duration from last cue
                    if raw_cues:
                        project.video_duration_seconds = raw_cues[-1]["end_time"]
                    await db.commit()

            # GIAI ĐOẠN 3: SPEAKER PROFILING (Character Matrix Analysis)
            if not start_stage or start_stage in ["INGESTING", "ASR_PROCESSING", "SPEAKER_PROFILING"]:
                spk_exist_res = await db.execute(select(func.count(SpeakerProfile.id)).where(SpeakerProfile.project_id == project_id))
                existing_spk_count = spk_exist_res.scalar() or 0

                if existing_spk_count > 0 and start_stage != "SPEAKER_PROFILING":
                    logger.info(f"Project {project_id} already has {existing_spk_count} speaker profiles. Skipping re-profiling.")
                else:
                    project.current_stage = "SPEAKER_PROFILING"
                    project.progress_percentage = 40
                    project.error_message = "Đang phân tích nhân vật và xây dựng ma trận quan hệ xưng hô..."
                    await db.commit()
                    await ws_manager.broadcast_to_project(project_id, "STAGE_CHANGED", {
                        "stage": "SPEAKER_PROFILING",
                        "progress": 40,
                        "message": "Đang phân tích nhân vật và xây dựng ma trận quan hệ xưng hô..."
                    })

                    cues_res = await db.execute(select(SubtitleCue).where(SubtitleCue.project_id == project_id).order_by(SubtitleCue.cue_index))
                    cues_list = cues_res.scalars().all()
                    cues_data = [
                        {"cue_index": c.cue_index, "text": c.original_text, "speaker": c.speaker_tag}
                        for c in cues_list
                    ]

                    analysis = await speaker_profiler.analyze_speakers_and_matrix(cues_data, project.source_language)
                    
                    # Update or insert speaker profiles
                    analysis_spks = analysis.get("speakers", {})
                    if isinstance(analysis_spks, list):
                        analysis_spks = {s.get("speaker_tag", f"SPEAKER_{i:02d}"): s for i, s in enumerate(analysis_spks) if isinstance(s, dict)}
                    elif not isinstance(analysis_spks, dict):
                        analysis_spks = {}

                    for spk_tag, spk_info in analysis_spks.items():
                        existing = await db.execute(select(SpeakerProfile).where(
                            SpeakerProfile.project_id == project_id,
                            SpeakerProfile.speaker_tag == spk_tag
                        ))
                        if not existing.scalar_one_or_none():
                            gender = spk_info.get("gender", "unknown")
                            default_spk_voice = "vi-VN-NamMinhNeural" if gender == "male" else (project.default_voice or "vi-VN-HoaiMyNeural")
                            db.add(SpeakerProfile(
                                project_id=project_id,
                                speaker_tag=spk_tag,
                                display_name=spk_info.get("display_name"),
                                gender=gender,
                                age_group=spk_info.get("age_group", "adult"),
                                role=spk_info.get("role"),
                                tone=spk_info.get("tone"),
                                tts_voice=spk_info.get("tts_voice") or default_spk_voice
                            ))

                    # Update or insert relationships
                    for rel in analysis.get("relationships", []):
                        existing_rel = await db.execute(select(RelationshipMatrix).where(
                            RelationshipMatrix.project_id == project_id,
                            RelationshipMatrix.source_speaker == rel["source_speaker"],
                            RelationshipMatrix.target_speaker == rel["target_speaker"]
                        ))
                        if not existing_rel.scalar_one_or_none():
                            db.add(RelationshipMatrix(
                                project_id=project_id,
                                source_speaker=rel["source_speaker"],
                                target_speaker=rel["target_speaker"],
                                self_pronoun=rel.get("self_pronoun", "Tôi"),
                                target_pronoun=rel.get("target_pronoun", "Bạn"),
                                relationship_type=rel.get("relationship_type", "Đồng nghiệp")
                            ))
                    await db.commit()

            # GIAI ĐOẠN 4: TRANSLATING (LLM Multi-Provider + Guardrails)
            if not start_stage or start_stage in ["INGESTING", "ASR_PROCESSING", "SPEAKER_PROFILING", "TRANSLATING"]:
                project.current_stage = "TRANSLATING"
                project.progress_percentage = 60
                project.error_message = "Đang dịch thuật phụ đề bằng AI đa ngữ cảnh..."
                await db.commit()
                await ws_manager.broadcast_to_project(project_id, "STAGE_CHANGED", {
                    "stage": "TRANSLATING",
                    "progress": 60,
                    "message": "Đang dịch thuật phụ đề bằng AI đa ngữ cảnh..."
                })

                # Fetch all cues, speakers, relationships, glossaries
                cues_res = await db.execute(select(SubtitleCue).where(SubtitleCue.project_id == project_id).order_by(SubtitleCue.cue_index))
                db_cues = cues_res.scalars().all()
                cues_payload = [
                    {
                        "id": c.id,
                        "cue_index": c.cue_index,
                        "start_time": c.start_time,
                        "end_time": c.end_time,
                        "original_text": c.original_text,
                        "speaker_tag": c.speaker_tag,
                        "target_speaker_tag": c.target_speaker_tag,
                        "translated_text": c.translated_text
                    }
                    for c in db_cues
                ]

                # Fetch speakers & matrix
                spk_res = await db.execute(select(SpeakerProfile).where(SpeakerProfile.project_id == project_id))
                speakers = {
                    s.speaker_tag: {
                        "name": s.display_name,
                        "original_name": getattr(s, 'original_name', '') or '',
                        "gender": s.gender,
                        "role": s.role,
                        "tone": s.tone,
                        "notes": s.notes
                    }
                    for s in spk_res.scalars().all()
                }
                
                rel_res = await db.execute(select(RelationshipMatrix).where(RelationshipMatrix.project_id == project_id))
                rels = [
                    {
                        "source_speaker": r.source_speaker,
                        "target_speaker": r.target_speaker,
                        "self_pronoun": r.self_pronoun,
                        "target_pronoun": r.target_pronoun,
                        "relationship_type": r.relationship_type,
                        "honorific_notes": r.honorific_notes
                    }
                    for r in rel_res.scalars().all()
                ]

                # Fetch glossary
                glo_res = await db.execute(select(GlossaryTerm).where(GlossaryTerm.project_id == project_id))
                glossary = [
                    {
                        "source_term": g.source_term,
                        "target_term": g.target_term,
                        "context_note": g.context_note
                    }
                    for g in glo_res.scalars().all()
                ]

                # Execute translation with real-time incremental DB saving
                cue_map = {c.cue_index: c for c in db_cues}

                async def save_batch_progress(batch_results, done_count, total_count):
                    for t in batch_results:
                        c_idx = t["cue_index"]
                        if c_idx in cue_map:
                            cue_map[c_idx].translated_text = t.get("translated_text")
                            cue_map[c_idx].cps = t.get("cps", 0.0)
                            cue_map[c_idx].line_count = t.get("line_count", 1)
                            cue_map[c_idx].max_line_length = t.get("max_line_length", 0)

                    pct = min(80, 60 + int((done_count / total_count) * 20))
                    project.progress_percentage = pct
                    project.error_message = f"Đang dịch thuật phụ đề bằng AI đa ngữ cảnh ({done_count}/{total_count} câu)..."
                    await db.commit()
                    await ws_manager.broadcast_to_project(project_id, "PROGRESS_UPDATE", {
                        "progress": pct,
                        "percentage": pct,
                        "message": project.error_message,
                        "translated_count": done_count,
                        "total_count": total_count
                    })

                translated_results = await translation_service.translate_project_cues(
                    project_id=project_id,
                    cues=cues_payload,
                    source_lang=project.source_language,
                    target_lang=project.target_language,
                    speaker_profiles=speakers,
                    relationship_matrix=rels,
                    glossary=glossary,
                    batch_callback=save_batch_progress
                )

                # Final ensure all translated cues are persisted
                for t in translated_results:
                    c_idx = t["cue_index"]
                    if c_idx in cue_map:
                        cue_map[c_idx].translated_text = t.get("translated_text")
                        cue_map[c_idx].cps = t.get("cps", 0.0)
                        cue_map[c_idx].line_count = t.get("line_count", 1)
                        cue_map[c_idx].max_line_length = t.get("max_line_length", 0)
                await db.commit()

                # Generate and write .ass and .srt files
                p_dir = storage_service.get_project_dir(project_id)
                proj_cfg = project.settings_override or {}
                bilingual_mode = proj_cfg.get("bilingual", False)
                sub_preset = proj_cfg.get("subtitle_preset", "box_banner")

                ass_content = subtitle_generator.generate_ass([
                    {
                        "start_time": c.start_time,
                        "end_time": c.end_time,
                        "original_text": c.original_text,
                        "translated_text": c.translated_text,
                        "speaker_tag": c.speaker_tag
                    }
                    for c in db_cues
                ], bilingual=bilingual_mode, preset=sub_preset)
                srt_content = subtitle_generator.generate_srt([
                    {
                        "start_time": c.start_time,
                        "end_time": c.end_time,
                        "original_text": c.original_text,
                        "translated_text": c.translated_text
                    }
                    for c in db_cues
                ])

                ass_path = p_dir / "subtitles.ass"
                srt_path = p_dir / "subtitles.srt"
                await storage_service.write_text_file(ass_path, ass_content)
                await storage_service.write_text_file(srt_path, srt_content)

                project.subtitles_ass_path = str(ass_path)
                project.subtitles_srt_path = str(srt_path)
                project.status = "WAITING_REVIEW"
                project.current_stage = "WAITING_REVIEW"
                project.progress_percentage = 80
                await db.commit()

                await ws_manager.broadcast_to_project(
                    project_id,
                    "STATUS_UPDATE",
                    {
                        "status": "WAITING_REVIEW",
                        "current_stage": "WAITING_REVIEW",
                        "progress": 80,
                        "message": "Translation completed. Ready for user studio review."
                    }
                )

        except Exception as e:
            logger.error(f"Pipeline error for project {project_id}: {e}", exc_info=True)
            project.status = "FAILED"
            
            # str(e) can be empty for built-in exceptions like NotImplementedError or ValueError()
            err_msg = str(e)
            if not err_msg:
                err_msg = f"Lỗi hệ thống ({type(e).__name__})"
                
            project.error_message = err_msg
            await db.commit()
            await ws_manager.broadcast_to_project(project_id, "PIPELINE_ERROR", {"error": err_msg})

    @classmethod
    async def burn_project_video(cls, db: AsyncSession, project_id: str):
        """Executes subtitle burning and final lossless stitching."""
        result = await db.execute(select(Project).where(Project.id == project_id))
        project = result.scalar_one_or_none()
        if not project:
            return

        try:
            project.status = "BURNING"
            project.current_stage = "BURNING"
            project.progress_percentage = 85
            project.error_message = "Đang render và gắn phụ đề cứng vào video (FFmpeg NVENC)..."
            await db.commit()
            await ws_manager.broadcast_to_project(project_id, "STAGE_CHANGED", {
                "stage": "BURNING",
                "progress": 85,
                "message": "Đang render và gắn phụ đề cứng vào video (FFmpeg NVENC)..."
            })

            p_dir = storage_service.get_project_dir(project_id)
            ass_path = Path(project.subtitles_ass_path) if project.subtitles_ass_path else p_dir / "subtitles.ass"
            video_path = None
            if project.dubbed_video_path and Path(project.dubbed_video_path).exists():
                video_path = Path(project.dubbed_video_path)
            elif (settings.OUTPUT_DIR / f"{project_id}_dubbed.mp4").exists():
                video_path = settings.OUTPUT_DIR / f"{project_id}_dubbed.mp4"
            elif project.local_video_path and Path(project.local_video_path).exists():
                video_path = Path(project.local_video_path)

            output_burned = p_dir / "output_burned.mp4"

            if not video_path or not video_path.exists():
                raise ValueError("Video nguồn không tồn tại. Vui lòng kiểm tra lại đường dẫn video.")

            cues_res = await db.execute(
                select(SubtitleCue).where(SubtitleCue.project_id == project_id).order_by(SubtitleCue.cue_index)
            )
            db_cues = cues_res.scalars().all()
            if not db_cues:
                raise ValueError("Dự án chưa có phụ đề. Vui lòng bấm 'Nhận diện & Dịch AI' trước khi burn video.")

            proj_cfg = project.settings_override or {}
            bilingual_mode = proj_cfg.get("bilingual", False)
            sub_preset = proj_cfg.get("subtitle_preset", "box_banner")
            mask_sub = proj_cfg.get("mask_original_sub", True)
            clean_mode = proj_cfg.get("clean_chinese_mode", "cinema_bars" if mask_sub else "none")
            top_mask_pct = float(proj_cfg.get("top_mask_pct", 11.0)) / 100.0
            bottom_mask_pct = float(proj_cfg.get("bottom_mask_pct", 15.0)) / 100.0

            # 1. Total Duration
            total_dur = project.video_duration_seconds
            if not total_dur or total_dur <= 0:
                total_dur = await asyncio.to_thread(asr_service.get_audio_duration, video_path)
                if not total_dur or total_dur <= 0:
                    total_dur = 3600.0  # Fallback

            CHUNK_DUR = 600.0  # 10 phút mỗi chunk
            num_chunks = max(1, int(total_dur // CHUNK_DUR) + (1 if total_dur % CHUNK_DUR > 0 else 0))
            sem = asyncio.Semaphore(2)  # Max 2 NVENC sessions concurrently

            async def process_chunk(idx: int):
                async with sem:
                    chunk_start = idx * CHUNK_DUR
                    chunk_dur = min(CHUNK_DUR, total_dur - chunk_start)
                    if chunk_dur <= 0.1: return None
                    
                    # Cập nhật tiến độ
                    pct = 85 + int(((idx + 1) / num_chunks) * 10)
                    project.progress_percentage = pct
                    project.error_message = f"Đang burn chunk {idx+1}/{num_chunks}..."
                    await db.commit()
                    await ws_manager.broadcast_to_project(project_id, "PROGRESS_UPDATE", {
                        "progress": pct, "percentage": pct, "message": project.error_message
                    })

                    # A. Cắt raw chunk
                    raw_chunk_path = p_dir / f"raw_chunk_{idx}.mp4"
                    ffmpeg_bin = settings.get_ffmpeg_bin()
                    cut_cmd = [
                        ffmpeg_bin, "-y", "-ss", str(chunk_start), "-t", str(chunk_dur),
                        "-i", str(video_path), "-c", "copy", str(raw_chunk_path)
                    ]
                    proc = await asyncio.create_subprocess_exec(*cut_cmd, stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.DEVNULL)
                    await proc.communicate()

                    # B. Tạo ASS cho chunk (đã offset thời gian)
                    chunk_cues = []
                    for c in db_cues:
                        if c.end_time >= chunk_start and c.start_time <= chunk_start + chunk_dur:
                            chunk_cues.append({
                                "start_time": max(0.0, c.start_time - chunk_start),
                                "end_time": c.end_time - chunk_start,
                                "original_text": c.original_text,
                                "translated_text": c.translated_text or c.original_text,
                                "speaker_tag": c.speaker_tag
                            })
                    
                    chunk_ass_path = p_dir / f"chunk_{idx}.ass"
                    chunk_ass_content = subtitle_generator.generate_ass(chunk_cues, bilingual=bilingual_mode, preset=sub_preset)
                    await storage_service.write_text_file(chunk_ass_path, chunk_ass_content)

                    # C. Burn phụ đề
                    burned_chunk_path = p_dir / f"burned_chunk_{idx}.mp4"
                    if raw_chunk_path.exists():
                        await video_burner.burn_subtitles_to_video(
                            video_path=raw_chunk_path,
                            ass_subtitle_path=chunk_ass_path,
                            output_video_path=burned_chunk_path,
                            mask_original_sub=mask_sub,
                            clean_chinese_mode=clean_mode,
                            top_mask_pct=top_mask_pct,
                            bottom_mask_pct=bottom_mask_pct
                        )
                    
                    # Dọn dẹp
                    if raw_chunk_path.exists(): raw_chunk_path.unlink()
                    if chunk_ass_path.exists(): chunk_ass_path.unlink()
                    
                    return burned_chunk_path

            tasks = [process_chunk(i) for i in range(num_chunks)]
            results = await asyncio.gather(*tasks)
            burned_chunks = [r for r in results if r and r.exists()]

            if burned_chunks:
                project.error_message = "Đang nối các chunk (Lossless Concat)..."
                await db.commit()
                await video_burner.lossless_concat_chunks(burned_chunks, output_burned)
                
                # Cleanup burned chunks
                for bc in burned_chunks:
                    if bc.exists(): bc.unlink()
            
            project.burned_video_path = str(output_burned)
            project.burned_video_url = storage_service.get_relative_url(output_burned)

            # Khôi phục ASS tổng để tải xuống (nếu có)
            ass_content = subtitle_generator.generate_ass([
                {
                    "start_time": c.start_time,
                    "end_time": c.end_time,
                    "original_text": c.original_text,
                    "translated_text": c.translated_text or c.original_text,
                    "speaker_tag": c.speaker_tag
                }
                for c in db_cues
            ], bilingual=bilingual_mode, preset=sub_preset)
            await storage_service.write_text_file(ass_path, ass_content)
            project.subtitles_ass_path = str(ass_path)

            project.status = "COMPLETED"
            project.current_stage = "COMPLETED"
            project.progress_percentage = 100
            await db.commit()

            await ws_manager.broadcast_to_project(
                project_id,
                "STATUS_UPDATE",
                {
                    "status": "COMPLETED",
                    "current_stage": "COMPLETED",
                    "progress": 100,
                    "burned_video_url": project.burned_video_url
                }
            )
        except Exception as e:
            logger.error(f"Burning error for project {project_id}: {e}", exc_info=True)
            project.status = "FAILED"
            project.error_message = str(e)
            await db.commit()
            await ws_manager.broadcast_to_project(project_id, "PIPELINE_ERROR", {"error": str(e)})


workflow_engine = WorkflowEngine()
