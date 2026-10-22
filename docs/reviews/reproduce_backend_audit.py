"""Read-only audit reproductions: isolated DB/files; no external API calls.

Run from the repository root:
    backend/.venv/Scripts/python.exe docs/reviews/reproduce_backend_audit.py
Assertions describe defects observed on 2026-10-21, not desired behavior.
"""

import asyncio
import ast
import io
import json
import logging
import os
import sys
import uuid
from pathlib import Path
from unittest.mock import AsyncMock, patch

ROOT = Path(__file__).resolve().parents[2]
ARTIFACTS = ROOT / "tmp" / "audit-2026-10-21" / "probes"
RUN_DIR = ARTIFACTS / uuid.uuid4().hex
os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///:memory:"
os.environ["OUTPUT_DIR"] = str(RUN_DIR / "outputs")
os.environ["UPLOAD_DIR"] = str(RUN_DIR / "uploads")
os.environ["TEMP_SCRATCH_DIR"] = str(RUN_DIR / "scratch")
sys.path.insert(0, str(ROOT / "backend"))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

import httpx
from fastapi import BackgroundTasks, UploadFile
from sqlalchemy import select

from app.agent.tools import agent_toolkit
from app.api.v1.pipeline import start_burning, trigger_pipeline
from app.database import AsyncSessionLocal, Base, engine, get_db
from app.main import app
from app.models.project import Project
from app.models.subtitle import SubtitleCue
from app.schemas.translation import BurnOptionsRequest, PipelineTriggerRequest
from app.services.asr_service import asr_service
from app.config import settings
from app.services.guardrails import SubtitleGuardrails
from app.services.llm_router import llm_router
from app.services.storage_service import storage_service
from app.services.translation_service import translation_service
from app.services.video_burner import video_burner
from app.services.workflow_engine import workflow_engine

logging.disable(logging.CRITICAL)
OBSERVATIONS = []


def record(name, **details):
    OBSERVATIONS.append({"check": name, **details})


async def isolated_db():
    async with AsyncSessionLocal() as session:
        yield session


async def main():
    # Avoid application lifespan: it invokes a separate hardcoded SQLite migrator.
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    app.dependency_overrides[get_db] = isolated_db

    async with AsyncSessionLocal() as db:
        project = Project(id="audit-project", title="isolated audit", status="PROCESSING")
        db.add(project)
        await db.commit()
        bg = BackgroundTasks()
        await trigger_pipeline(project.id, PipelineTriggerRequest(), bg, db)
        await trigger_pipeline(project.id, PipelineTriggerRequest(), bg, db)
        assert len(bg.tasks) == 2
        record("duplicate_trigger", active_status=project.status, queued_tasks=len(bg.tasks))

        # No FFmpeg/paid work occurs: the missing global fails before media processing.
        await workflow_engine.burn_project_video(db, project.id)
        assert project.status == "FAILED" and "settings" in project.error_message
        record("burn_missing_import", status=project.status, error=project.error_message)

        project.settings_override = {"subtitle_preset": "cinema", "bilingual": False}
        await db.commit()
        await start_burning(project.id, BackgroundTasks(), BurnOptionsRequest(bilingual=True), db)
    async with AsyncSessionLocal() as db:
        project = (await db.execute(select(Project).where(Project.id == "audit-project"))).scalar_one()
        assert project.settings_override["bilingual"] is False
        record("burn_options_json_mutation_not_saved", requested_bilingual=True,
               persisted_bilingual=project.settings_override["bilingual"])

    transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)
    async with httpx.AsyncClient(transport=transport, base_url="http://audit") as client:
        response = await client.post("/api/v1/projects/audit-project/glossary/auto-extract")
        assert response.status_code == 500
        record("glossary_auto_extract", http_status=response.status_code)
        response = await client.get("/api/v1/projects")
        assert response.status_code == 200
        record("unauthenticated_project_list", http_status=response.status_code)
        response = await client.post(
            "/api/v1/projects/audit-project/reset-status", json={"target_status": "CREATED"}
        )
        assert response.json()["status"] == "WAITING_REVIEW"
        record("reset_json_body_ignored", requested="CREATED", actual=response.json()["status"])

        # Sending only the final chunk is accepted as a completed upload.
        response = await client.post(
            "/api/v1/projects/audit-project/upload-chunk",
            data={"filename": "audit.mp4", "chunk_index": 1, "total_chunks": 2,
                  "offset": 10, "auto_start_pipeline": "false"},
            files={"file": ("audit.mp4", b"tail", "video/mp4")},
        )
        assert response.status_code == 200
        saved = Path(response.json()["local_video_path"])
        assert saved.read_bytes() == b"\0" * 10 + b"tail"
        record("incomplete_chunk_upload_accepted", http_status=response.status_code,
               file_bytes=saved.stat().st_size, missing_prefix_bytes=10)

        # Overwriting at offset zero does not truncate the previous upload's tail.
        await storage_service.write_upload_chunk(
            "audit-project", "audit.mp4", UploadFile(file=io.BytesIO(b"new")), 0
        )
        assert saved.read_bytes().startswith(b"new") and saved.stat().st_size == 14
        record("replacement_upload_retains_tail", new_input_bytes=3, actual_bytes=saved.stat().st_size)

    audio = ARTIFACTS / "probe.wav"
    audio.parent.mkdir(parents=True, exist_ok=True)
    audio.write_bytes(b"dummy nonempty audio for injected failure")
    with patch.object(asr_service, "_get_or_load_model", side_effect=RuntimeError("injected ASR failure")):
        cues = await asr_service.transcribe_audio(audio)
    assert len(cues) == 2 and cues[0]["original_text"].startswith("大家")
    record("asr_failure_returns_demo", cues=len(cues), first_text=cues[0]["original_text"])

    cue = {"cue_index": 1, "original_text": "Hello", "start_time": 0., "end_time": 4.}
    with patch.object(llm_router, "generate_completion", AsyncMock(side_effect=RuntimeError("offline"))):
        translated = await translation_service.translate_project_cues("audit", [cue])
    assert translated[0]["translated_text"] == "Hello"
    assert translated[0]["has_guardrail_violation"] is False
    record("translation_failure_accepted", text=translated[0]["translated_text"],
           violation=translated[0]["has_guardrail_violation"])

    corrected = json.dumps({"translations": [{"id": 1, "text": "Xin chào"}]})
    with patch.object(llm_router, "generate_completion", AsyncMock(side_effect=["invalid json", corrected])):
        translated = await translation_service.translate_project_cues("audit", [cue])
    assert translated[0]["translated_text"] == "Hello"
    record("reflexion_valid_repair_discarded", expected_repair="Xin chào", actual=translated[0]["translated_text"])

    requested = [{"id": 1, "text": "hello", "duration": 20.}]
    long_text = " ".join(["word"] * 40)
    valid, translations, violations = SubtitleGuardrails.validate_batch(
        requested, json.dumps({"translations": [{"id": 1, "text": long_text}]})
    )
    assert valid and len(translations[0].text.split()) < 40
    record("guardrail_silent_truncation", input_words=40,
           output_words=len(translations[0].text.split()), valid=valid, violations=violations)

    requested = [{"id": 1, "text": "hey", "duration": 4.,
                  "speaker": "A", "target_speaker": "B"}]
    raw = json.dumps({"translations": [{"id": 1, "text": "Mày làm gì?"}]})
    matrix_dict = {"A_to_B": {"self": "Anh", "target": "Em"}}
    matrix_list = [{"source_speaker": "A", "target_speaker": "B",
                    "self_pronoun": "Anh", "target_pronoun": "Em"}]
    valid_dict, _, _ = SubtitleGuardrails.validate_batch(requested, raw, matrix_dict)
    valid_list, _, _ = SubtitleGuardrails.validate_batch(requested, raw, matrix_list)
    assert not valid_dict and valid_list
    record("pronoun_guard_skipped_for_db_list", dict_valid=valid_dict, db_list_valid=valid_list)

    with patch.object(llm_router, "generate_completion", AsyncMock()) as completion:
        result = await translation_service.translate_project_cues(
            "audit", [{**cue, "translated_text": "old translation"}],
            custom_instructions="Translate again with new instructions"
        )
        assert completion.await_count == 0
        record("pipeline_retranslate_skips_existing_text", provider_calls=0,
               retained_text=result[0]["translated_text"])

    try:
        await agent_toolkit.execute("generate_dubbing_audio", {"text": "audit text"})
    except AttributeError as exc:
        assert "preview_voice" in str(exc)
        record("agent_tts_missing_method", error=str(exc))
    else:
        raise AssertionError("Expected missing TTS method")
    result = await agent_toolkit.execute("translate_subtitle_chunk", {"cues": [{"id": 1, "text": "Hello"}]})
    assert "translations" not in result and result["user_prompt_ready"]
    record("agent_translate_only_builds_prompt", returned_keys=list(result))

    # Demonstrate rendering failure being returned as successful source copy.
    source = ARTIFACTS / "source.mp4"
    source.write_bytes(b"original video bytes")
    ass = ARTIFACTS / "test.ass"
    ass.write_text("invalid ASS", encoding="utf-8")
    output = ARTIFACTS / "burned.mp4"
    failed_process = AsyncMock()
    failed_process.returncode = 1
    failed_process.communicate.return_value = (b"", b"injected ffmpeg failure")
    with patch.object(video_burner, "detect_best_encoder", AsyncMock(return_value="libx264")), \
            patch("asyncio.create_subprocess_exec", AsyncMock(return_value=failed_process)):
        await video_burner.burn_subtitles_to_video(source, ass, output)
    assert output.read_bytes() == source.read_bytes()
    record("burn_failure_copies_original", returned_normally=True, identical_bytes=True)

    # Pipeline overwrites actual media duration with last dialogue timestamp.
    async with AsyncSessionLocal() as db:
        project = (await db.execute(select(Project).where(Project.id == "audit-project"))).scalar_one()
        project.video_duration_seconds = 12.
        project.extracted_audio_path = str(audio)
        project.local_video_path = str(source)
        await db.commit()
        with patch.object(asr_service, "transcribe_audio", AsyncMock(return_value=[{
            "cue_index": 1, "start_time": 0., "end_time": 4.,
            "original_text": "Hello", "speaker_tag": "SPEAKER_00"
        }])), patch.object(llm_router, "generate_completion", AsyncMock(return_value=corrected)):
            await workflow_engine.run_pipeline(db, project.id, start_stage="ASR_PROCESSING")
        assert project.video_duration_seconds == 4. and project.status == "WAITING_REVIEW"
        record("media_duration_replaced_by_dialogue_end", original_duration=12.,
               stored_duration=project.video_duration_seconds, status=project.status)

    # Validate exact missing module globals without running downloader/network.
    projects_tree = ast.parse((ROOT / "backend/app/api/v1/projects.py").read_text(encoding="utf-8"))
    globals_imports = {alias.asname or alias.name.split(".")[0]
                       for node in projects_tree.body if isinstance(node, ast.Import)
                       for alias in node.names}
    assert "asyncio" not in globals_imports
    record("download_progress_missing_asyncio", module_import_present=False)

    # Exercise the two-chunk path with a dubbed input, which bypasses the missing
    # settings lookup at line 389. Supply only that missing global in memory so
    # the independent shared-session bug can be observed without changing source.
    import importlib
    workflow_module = importlib.import_module("app.services.workflow_engine")
    async with AsyncSessionLocal() as db:
        project = (await db.execute(select(Project).where(Project.id == "audit-project"))).scalar_one()
        project.dubbed_video_path = str(source)
        project.video_duration_seconds = 1200.
        await db.commit()

        async def fake_process(*args, **kwargs):
            Path(args[-1]).write_bytes(b"fake video chunk")
            process = AsyncMock()
            process.returncode = 0
            process.communicate.return_value = (b"", b"")
            return process

        async def fake_burn(**kwargs):
            kwargs["output_video_path"].write_bytes(b"fake burned chunk")

        async def fake_concat(paths, output_path):
            output_path.write_bytes(b"fake concat")

        with patch.object(workflow_module, "settings", settings, create=True), \
                patch("asyncio.create_subprocess_exec", fake_process), \
                patch.object(video_burner, "burn_subtitles_to_video", fake_burn), \
                patch.object(video_burner, "lossless_concat_chunks", fake_concat):
            try:
                await workflow_engine.burn_project_video(db, project.id)
            except Exception as exc:
                record("parallel_burn_shared_session_error", error_type=type(exc).__name__, error=str(exc))
                await asyncio.sleep(0.05)
                await db.rollback()
            else:
                raise AssertionError("Expected shared-session transaction error in parallel burn")

    await engine.dispose()
    destination = ARTIFACTS / "results.json"
    destination.write_text(json.dumps(OBSERVATIONS, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"reproduced": len(OBSERVATIONS), "checks": OBSERVATIONS}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
