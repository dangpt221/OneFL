import logging
import asyncio
from pathlib import Path
from typing import Optional, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete, func
from app.config import settings

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
        start_stage: Optional[str] = None,
        force_reprocess: bool = False
    ):
        """Executes pipeline asynchronously with status updates and error handling."""
        if start_stage not in {None, "INGESTING", "ASR_PROCESSING", "SPEAKER_PROFILING", "TRANSLATING"}:
            raise ValueError("Invalid pipeline stage")
        # Fetch project
        result = await db.execute(select(Project).where(Project.id == project_id))
        project = result.scalar_one_or_none()
        if not project:
            logger.error(f"Project {project_id} not found.")
            return

        try:
            from app.services.artifact_service import invalidate_artifacts
            invalidate_artifacts(project, audio=True)
            project.status = 'PROCESSING'
            await db.commit()
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
                if not video_path or not video_path.is_file():
                    raise ValueError("Source video is missing")
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
                if existing_cues_count and start_stage == "ASR_PROCESSING" and not force_reprocess:
                    raise ValueError("Re-running ASR requires force_reprocess=true")

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
                    if force_reprocess and start_stage == 'ASR_PROCESSING':
                        await db.execute(delete(RelationshipMatrix).where(RelationshipMatrix.project_id == project_id))
                        await db.execute(delete(SpeakerProfile).where(SpeakerProfile.project_id == project_id))
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
                    
                    # Keep duration from the source media, including silence.
                    if not raw_cues:
                        raise ValueError("No speech detected; no subtitle content was generated")
                    if not project.video_duration_seconds:
                        project.video_duration_seconds = await asyncio.to_thread(asr_service.get_audio_duration, Path(project.local_video_path))
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

                    analysis = await speaker_profiler.analyze_speakers_and_matrix(cues_data, project.source_language) if settings.ENABLE_SPEAKER_PROFILER else {"speakers": {}, "relationships": []}
                    
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
                if not db_cues:
                    raise ValueError('No transcript cues available for translation')
                cues_payload = [
                    {
                        "id": c.id,
                        "cue_index": c.cue_index,
                        "start_time": c.start_time,
                        "end_time": c.end_time,
                        "original_text": c.original_text,
                        "speaker_tag": c.speaker_tag,
                        "target_speaker_tag": c.target_speaker_tag,
                        "translated_text": c.translated_text,
                        "is_edited": c.is_edited
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
                        "priority": g.priority, "case_sensitive": g.case_sensitive, "context_note": g.context_note
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
                            cue_map[c_idx].has_guardrail_violation = t.get("has_guardrail_violation", False)
                            cue_map[c_idx].violation_notes = t.get("violation_notes")

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
                    batch_callback=save_batch_progress,
                    force_reprocess=force_reprocess,
                    model_override=(project.settings_override or {}).get("model_override"),
                    video_context=(project.settings_override or {}).get("video_context"),
                    video_path=project.local_video_path,
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
            logger.exception("Pipeline failed for %s", project_id)
            await db.rollback()
            from sqlalchemy import update
            await db.execute(update(Project).where(Project.id == project_id).values(status='FAILED', error_message=str(e) or type(e).__name__))
            await db.commit()
            await ws_manager.broadcast_to_project(project_id, 'PIPELINE_ERROR', {'status': 'FAILED', 'error': str(e) or type(e).__name__})
            raise

    @classmethod
    async def burn_project_video(cls, db: AsyncSession, project_id: str):
        """Render accurate source intervals; only the coordinator writes the DB."""
        import hashlib
        import json
        import math
        import uuid
        from app.services.media_process import probe_media, validate_duration
        from app.services.artifact_service import invalidate_artifacts
        from sqlalchemy import update
        project = await db.get(Project, project_id)
        if not project:
            raise ValueError('Project not found')
        tasks = []
        try:
            video_path = Path(project.dubbed_video_path or project.local_video_path or '')
            duration = await probe_media(video_path, require_video=True)
            project.video_duration_seconds = duration
            cues = (await db.execute(select(SubtitleCue).where(SubtitleCue.project_id == project_id).order_by(SubtitleCue.start_time, SubtitleCue.cue_index))).scalars().all()
            if not cues or any(not c.translated_text for c in cues):
                raise ValueError('All subtitle cues must be translated before burning')
            cfg = dict(project.settings_override or {})
            payload = [{'start_time': c.start_time, 'end_time': c.end_time, 'original_text': c.original_text,
                        'translated_text': c.translated_text, 'speaker_tag': c.speaker_tag} for c in cues]
            signature = hashlib.sha256(json.dumps([str(video_path.resolve()), video_path.stat().st_mtime_ns, payload, cfg], sort_keys=True).encode()).hexdigest()[:24]
            p_dir = storage_service.get_project_dir(project_id)
            chunk_dir = p_dir / 'render' / signature
            chunk_dir.mkdir(parents=True, exist_ok=True)
            invalidate_artifacts(project)
            project.status, project.current_stage, project.progress_percentage = 'BURNING', 'BURNING', 85
            await db.commit()
            chunk_duration = float(settings.VIDEO_CHUNK_DURATION_SECONDS)
            if chunk_duration <= 0:
                raise ValueError('VIDEO_CHUNK_DURATION_SECONDS must be positive')
            count = math.ceil(duration / chunk_duration)
            semaphore = asyncio.Semaphore(max(1, settings.MAX_CONCURRENT_GPU_BURN_WORKERS))

            async def render(index):
                async with semaphore:
                    start = index * chunk_duration
                    length = min(chunk_duration, duration - start)
                    output = chunk_dir / f'{index}.mp4'
                    if output.is_file():
                        try:
                            await validate_duration(output, length, video=True)
                            return index, output
                        except (RuntimeError, OSError):
                            logger.warning('Invalid render checkpoint %s; regenerating', output.name)
                    ass_path = chunk_dir / f'{index}.ass'
                    chunk_cues = [{**c, 'start_time': max(0., c['start_time'] - start), 'end_time': min(length, c['end_time'] - start)}
                                  for c in payload if c['end_time'] > start and c['start_time'] < start + length]
                    await storage_service.write_text_file(ass_path, subtitle_generator.generate_ass(chunk_cues, bilingual=cfg.get('bilingual', False), preset=cfg.get('subtitle_preset', 'cinema')))
                    temporary = output.with_name(f'{index}.partial.mp4')
                    try:
                        await video_burner.burn_subtitles_to_video(
                            video_path, ass_path, temporary,
                            mask_original_sub=cfg.get('mask_original_sub', True),
                            clean_chinese_mode=cfg.get('clean_chinese_mode', 'cinema_bars'),
                            top_mask_pct=cfg.get('top_mask_pct', 11.) / 100,
                            bottom_mask_pct=cfg.get('bottom_mask_pct', 15.) / 100,
                            start_time=start, duration=length,
                        )
                        await validate_duration(temporary, length, video=True)
                        temporary.replace(output)
                        return index, output
                    finally:
                        temporary.unlink(missing_ok=True)
                        ass_path.unlink(missing_ok=True)

            tasks = [asyncio.create_task(render(index)) for index in range(count)]
            results = {}
            for finished in asyncio.as_completed(tasks):
                index, path = await finished
                results[index] = path
                project.progress_percentage = 85 + int(len(results) / count * 10)
                project.error_message = f'Burned {len(results)}/{count} chunks'
                await db.commit()
                await ws_manager.broadcast_to_project(project_id, 'PROGRESS_UPDATE', {'stage': 'BURNING', 'progress': project.progress_percentage, 'message': project.error_message})
            if len(results) != count:
                raise RuntimeError('Missing rendered chunks')
            output = p_dir / f'output_{uuid.uuid4().hex}.mp4'
            await video_burner.lossless_concat_chunks([results[i] for i in range(count)], output)
            await validate_duration(output, duration, video=True)
            project.burned_video_path, project.burned_video_url = str(output), storage_service.get_relative_url(output)
            project.status, project.current_stage, project.progress_percentage = 'COMPLETED', 'COMPLETED', 100
            project.error_message = None
            await db.commit()
            await ws_manager.broadcast_to_project(project_id, 'STATUS_UPDATE', {'status': 'COMPLETED', 'current_stage': 'COMPLETED', 'progress': 100, 'burned_video_url': project.burned_video_url})
        except BaseException as error:
            for task in tasks:
                if not task.done():
                    task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)
            await db.rollback()
            if isinstance(error, Exception):
                logger.exception('Burn failed for %s', project_id)
                await db.execute(update(Project).where(Project.id == project_id).values(status='FAILED', error_message=str(error) or type(error).__name__))
                await db.commit()
                await ws_manager.broadcast_to_project(project_id, 'PIPELINE_ERROR', {'status': 'FAILED', 'error': str(error)})
            raise


workflow_engine = WorkflowEngine()
