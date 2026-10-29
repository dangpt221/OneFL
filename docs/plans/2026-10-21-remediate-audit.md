# Audit remediation Implementation Plan

**Goal:** Fix F01–F28 and the operational defects documented in the audit, retaining current user edits and validating actual behavior.
**Architecture:** Keep the current FastAPI/Next.js application, introduce a durable DB-backed single-host job queue with atomic project ownership, cancel/recovery, and bounded resource admission. Keep media on local disk; process PCM in bounded blocks, verify artifacts, and reject failed or incomplete work. Do not claim optional distributed/multimodal capabilities without implementing and validating their configured paths.
**Tech Stack:** Python, FastAPI, SQLAlchemy async, Pydantic V2, FFmpeg, Next.js/React/TypeScript; existing dependencies plus explicitly declared media dependencies.

## Constraints and file impact

Modify backend services/routes/models/schemas/config/database, frontend API/socket/components, Docker/dependency/ignore/startup configuration, dataset generation/evaluation and architecture documentation. Create regression tests, media/job/security helpers, migration support, and a final F01–F28 closure record. Existing audit evidence is historical and retained. No destructive Git operations, live video runs, paid API calls, or real-database migration during verification.

Paths below are relative to [D:/OneFl](/D:/OneFl). Existing line ranges refer to the pre-change audit inventory; new modules start at line 1. Each numbered reading/editing/check action is a small execution slice, split further when tests expose another defect.

## Atomic tasks and verification

1. Create `tests/test_reliability.py`: regression assertions for failure propagation, content preservation, matrix normalization, repair merge, duration, burn/concat output. Run `backend/.venv/Scripts/python.exe -m pytest tests/test_reliability.py -q -p no:cacheprovider`; expect failures demonstrating audited behavior before implementation.
2. Add isolated DB/storage fixtures in the new tests; verify no writes to user DB/media, run selected API tests.
3. Modify `backend/app/services/guardrails.py:25-228`: preserve all words, report line/count/CPS/schema/ID violations, normalize matrix and glossary contracts. Verify guardrail regression tests.
4. Modify `translation_service.py:19-230`: distinguish resume/force, honor model/temperature, merge missing repairs, revalidate, fail unresolved batches and persist QC. Verify mocked offline/malformed/partial/repaired cases.
5. Create `services/media_process.py`: bounded async subprocess execution, timeout/cancel kill, media probing and output validation. Test actual short FFmpeg media and injected failures.
6. Modify `audio_service.py:19-75` and `asr_service.py:44-194`: strict failure/no-speech handling, model admission lock, duration/progress validation, chunk checkpoint and cleanup; remove fake speaker alternation. Verify inference/no-speech/failure/checkpoint tests.
7. Modify `video_burner.py:20-259`: strict encode/concat, CPU retry, stream/duration validation, timeout/process cleanup; no source-copy success. Verify render and concat error tests plus small actual media smoke.
8. Modify `workflow_engine.py:30-365`: preserve media duration, validate stages, invalidate outputs, persist QC, rollback before failure, honor force/edited policy. Verify pipeline regression tests.
9. Modify `workflow_engine.py:365-538`: render accurate source intervals, serialize DB commits, global admission, deterministic checkpoint names, require every chunk and final artifact. Verify two-chunk concurrency and trailing-silence media.
10. Add bounded PCM mixer helper and modify `tts_service.py:615-880`: decode one clip at a time to scratch, overlap-add in fixed blocks off event loop, stream encode; verify audio overlap/duration and bounded block allocation.
11. Modify `tts_service.py:355-610`: strict synthesis/provider selection, no silent fallbacks, safe preview/cache keys; verify provider error and preview/cache tests.
12. Modify TTS tempo/cache/mux and `tts.py:64-301`: time/model-aware keys, actual adjusted duration, cue success counts, speaker speed, saved resume config, output invalidation. Verify failure/retime/resume settings tests.
13. Add durable `models/job.py` and `services/job_service.py`: atomic claim, persisted payload, heartbeat, cancellation, restart queue recovery, bounded dispatch. Add job regressions, observe red then green.
14. Route pipeline, URL ingestion, upload finalize and dubbing through job submission; cancel before reset/delete. Verify duplicate/cancel/recovery integration tests.
15. Modify `storage_service.py:20-102`: contained paths, atomic text writes, immutable upload sessions/manifests and checksums, offset retry validation, finalization and quota. Test missing/out-of-order/retry/replacement chunks.
16. Modify `projects.py:230-305` and frontend `lib/api.ts:29-65`: resumable upload ID/status/finalize, bounded retries; verify API upload regression tests.
17. Modify `database.py:62-100`, `db_migrator.py:1-52`: one DSN, introspected/versioned migrations, no silent fallback or swallowed DDL, foreign keys; verify isolated old-schema upgrade/idempotence tests.
18. Modify schemas/model constraints (`schemas/subtitle.py:6-25`, translation/project schemas): finite times/end>start, IDs/enums/ranges/null policy, project cue uniqueness on new schemas; verify 422/update validation.
19. Modify `subtitles.py:25-373`: all CRUD sync, rollback/error mapping, artifact invalidation and stable timing ordering, request override propagation. Verify CRUD/export integration tests.
20. Modify `glossary.py:309-394`, `speakers.py` import/upserts and pipeline context: import func, no silent AI failure, deduplicate imports, consistent target inference. Verify endpoint/provider/duplicate tests.
21. Modify `agent/tools.py:175-399`: invoke actual translate/burn/TTS services, return full results/artifacts, scope filesystem paths. Verify functional Agent tool tests with provider mocks.
22. Add access control/session routes and guard HTTP/static/WebSocket/URL ingestion, bounded job/API admission. Default local development to loopback; require configured credentials in production. Verify unauthenticated denial, allowed session, cross-origin and network-target tests.
23. Modify `main.py:34-96`, `ws_manager.py:13-60`, websocket route: lifespan queue recovery/shutdown, readiness probes, normalized failure/snapshot events and bounded send. Verify websocket/status/readiness tests.
24. Modify frontend `CreateProjectModal.tsx:33-72`, `GlossaryModal.tsx:63-85`, `app/page.tsx:17-34`: stable hook order and polling lifecycle. Run React regression script red then green and TypeScript.
25. Modify `lib/useWebSocket.ts:17-70`, Studio page: same-origin socket proxy, clean teardown, failure/reconnect snapshot, translated batch updates with global progress. Run frontend contract regressions and build.
26. Modify DubbingModal/types, glossary CSV import, status/download/preview settings and action errors. Run TypeScript, frontend regression checks and production build.
27. Align requirements/pyproject, Docker root/layout/proxy/ignore/public, launchers and Git ignore scopes. Validate manifest coverage, `git check-ignore`, TypeScript/build and Docker config/build when available; report environmental limits honestly.
28. Remove synthetic glossary terms and duplicate benchmark claims; generate independent deduplicated fixtures and measure actual scope. Replace old count-only assertions with meaningful fixture/rule tests. Verify dataset generation/evaluation and tests.
29. Update Architecture/spec/README operational scope, job recovery/security/setup and manual script configuration; mark optional diarization/visual/distributed capabilities accurately and test any implemented integration adapters with mocks.
30. Run full isolated Python tests, actual short-media integration, syntax/lint available tools, TypeScript/frontend regressions/build; create `docs/reviews/2026-10-21-remediation-results.md` mapping every finding to code/tests/remaining external validation. Update SESSION_STATE at each milestone.

## Review checkpoint and fallback

The user explicitly authorized fixing all audited defects. Continue through implementation and verification without asking for approval again. Checkpoints are progress/evidence updates. Do not silently reduce the scope; record incomplete external validation separately from code fixes. If optional services/models are unavailable, exercise integration contracts with mocks and fail explicitly when the real capability is requested without configuration. Preserve user data and the existing working tree; do not create commits or run migrations against the real DB automatically.

## Execution record

- [x] Tasks 1–12: strict translation/QC/ASR/media duration and bounded PCM/TTS/render processing; regressions and real short-media checks.
- [x] Tasks 13–23: durable queue, cancellation/recovery, resumable upload, schema/migrations, API/Agent, access control and WS snapshots.
- [x] Tasks 24–28: frontend hooks/polling/CSV/timeline/contracts, dependency/deployment/ignore fixes, independent fixture/glossary cleanup.
- [x] Task 29: operating guide, backend README, architecture/spec implementation boundaries and API-based manual script.
- [x] Task 30: 92 tests pass (one dependency deprecation warning), real FFmpeg integration, 82 Python syntax checks, frontend regression/TypeScript/production build, YAML/manifests, per-finding closure record and session ledger.
- Docker/Compose and live PostgreSQL/AI/GPU/browser/10h checks remain external validation limits, documented in the closure record. Docker/Ruff were unavailable. CI is added for future clean-checkout execution.
