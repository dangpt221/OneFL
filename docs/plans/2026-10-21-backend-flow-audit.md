# OneFL backend and end-to-end flow audit

## Goal
Review the current working tree, trace every first-party application module, and report actionable defects with file/line evidence and reproducible checks. Review only: do not change application code or live project data.

## Architecture & constraints
Compare implementation with Architecture.md and Translation_Engine_Specification.md, especially 10h/50GB resource bounds, async blocking, durable jobs, WebSocket consistency, cleanup and Windows paths. Existing uncommitted changes belong to the user and must remain intact. External paid APIs and long GPU jobs are outside local validation.

## File impact matrix
| Action | Target |
|---|---|
| Create | docs/plans/2026-10-21-backend-flow-audit.md |
| Create | docs/reviews/2026-10-21-backend-flow-audit.md |
| Append | .agents/SESSION_STATE.md (preserve prior history) |
| Read/test | backend/app, frontend/src, tests, scripts, Docker/startup files |

## Atomic review tasks
Each reading slice is approximately 2–5 minutes; subdivide long services by function. No application signatures are changed.

1. Read backend/app/main.py:1-110, config.py:1-190, database.py:1-120 and model/schema modules. Verify registration, configuration and persistence through `rg -n 'include_router|create_async_engine|ForeignKey|relationship' backend/app`; record actual invariants.
2. Read backend/app/api/v1/projects.py and pipeline.py in numbered slices. Trace create/upload/download/start/reset/delete and task session lifetime. Verify with `rg -n 'BackgroundTasks|create_task|reset|delete|commit' backend/app/api/v1`; identify concrete concurrency/failure paths.
3. Read workflow_engine.py by run_pipeline/burn_project_video, audio_service.py, asr_service.py and storage_service.py. Verify chunking, timestamps, failure checks and bounded resources using numbered source and isolated probes.
4. Read translation_service.py, llm_router.py, prompt_builder.py, speaker_profiler.py and guardrails.py by function. Trace batch IDs, resume/context, retries and validation; verify with existing guardrail/dataset tests plus isolated mock probes.
5. Read tts.py and tts_service.py by endpoint/synthesis/mixing/cache function; inspect state transitions, voice selection and RAM use. Verify using existing tests and mock-only checks.
6. Read all remaining API, agent, WebSocket, subtitle and preset modules. Verify object scoping, tool capabilities, error handling and export contract using source evidence and isolated calls.
7. Read every frontend source module; compare request bodies, events, settings and editing/export behavior with backend. Inspect scripts, Dockerfiles, compose and launchers for runnable dependency/configuration paths.
8. Inspect tests before execution. Run `backend/.venv/Scripts/python.exe -m pytest tests -q -p no:cacheprovider` and frontend TypeScript/build checks when safe. Expected baseline: report exact exit/count, including failures; never infer production readiness from pass count.
9. Create the review report with actual flow, severity-ranked findings, validation evidence, coverage gaps and remediation order. Verify report references against `rg -n` output, update the ledger with evidence.

## Review checkpoint & fallback
The user's request authorizes this read-only audit and local non-destructive validation. Proceed through review without an approval pause. Report findings for review before any application fixes. If a check requires live data mutation, paid calls, unavailable services or unsafe startup migrations, replace it with an isolated mock/static check and clearly record the limit.
