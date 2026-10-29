# Agent Tool Completion Plan

**Goal:** Close AT01–AT08, make Agent media work use the existing durable project queue, add project/job tools and two focused repository skills with regression evidence.

**Architecture & constraints:** Single-host DB lease/OS lock remains authoritative. Existing lightweight analysis/preview tools remain bounded request operations; ASR/burn become asynchronous project jobs with durable result metadata. Preserve ownership checks, version artifacts and DB/WebSocket synchronization. No live DSN/provider/model calls in validation, no new external framework or paid integration. Full long-media quality/load claims remain out of scope.

## File impact matrix

| Action | File / scope |
|---|---|
| Modify | [tools](/D:/OneFl/backend/app/agent/tools.py:24), [Runner](/D:/OneFl/backend/app/agent/agent_runner.py:107), [API](/D:/OneFl/backend/app/api/v1/agent.py:20) |
| Modify | [job model](/D:/OneFl/backend/app/models/job.py:9), [worker](/D:/OneFl/backend/app/services/job_service.py:30), [profiler](/D:/OneFl/backend/app/services/speaker_profiler.py:21), migration version, tracker for ASR-only workflow |
| Create | `backend/app/agent/contracts.py`, `backend/app/services/agent_project_service.py`, `tests/test_agent_completion.py` |
| Create | `.agents/skills/onefl-agent-tools/SKILL.md`, `.agents/skills/onefl-media-verification/SKILL.md` |
| Update | Agent tests/count contract, README/API guide, review closure record, session ledger |

## Atomic tasks and verification

1. Add failing regressions for ASR/profile aliases, list relationships, QC accepted counts, malformed decisions and false success. `pytest tests/test_agent_completion.py -q ...` must reproduce the audit failures before implementation.
2. Define bounded typed inputs/outcomes and normalize cue/relationship data. Fix QC accepted/rejected fields, real inspection, TTS model/speed and export bilingual behavior. Repeat focused tests: these contracts must pass.
3. Add persisted `Job.result`; implement owned project lookup and AGENT_TOOL admission/execution for ASR and burn. Worker restores owner context, stores results and releases ownership through existing lifecycle. Tests must show duplicate claim 409, foreign project denial, no direct render, cancellation and restart-safe payload.
4. Implement ASR extraction/persistence with explicit replacement authorization, project export artifacts and validated existing-ASS burn. Remove misleading burn preset field; preset belongs to export/project burn options. Verify file handoff and current artifact metadata in isolated DB.
5. Add six tools: get_project_context, start_project_pipeline, dub_project_video, get_job_status, wait_for_job, cancel_project_job. Reuse existing request schemas/admission. Verify ownership, paginated context, bounded waits and durable job state.
6. Validate Runner decision JSON before dispatch; bound context/observations/history and distinguish PENDING/FAILED/COMPLETED. Check queued jobs/artifacts before success. API preserves HTTP errors. Targeted tests must reject malformed shapes gracefully and avoid treating queued or failed work as completed.
7. Run an isolated end-to-end Agent/project test from synthetic video → ASR → translation/export → burn with real FFmpeg and mocked external providers. Assert DB cue/output refs, job result and snapshots, not just function-call counts.
8. Add the two repository skills, describe concrete tool/job contracts and reproducible verification commands; validate with skill-creator quick_validate. Do not install unrelated skills or external services.
9. Run full isolated pytest, frontend regressions/TypeScript/build if tracker changes, Python compile and diff check. Update AT01–AT08 closure matrix, tool catalog, README and session ledger with actual evidence and limits.

Commands run from repository root, with `$env:DATABASE_URL='sqlite+aiosqlite:///:memory:'`, `backend/.venv/Scripts/python.exe -m pytest ... -p no:cacheprovider --basetemp=tmp/agent-completion-*`. Expected final outcome: all acceptance tests pass, real short-media pipeline produces a valid referenced output, skills validate, no user DB writes. User already authorized implementation and additions; progress updates serve as checkpoints, no additional approval gate.

## Execution record

- [x] Tasks 1–2: observed 11 failing regressions before implementation; canonical cue/timing/relationship and output/decision models, QC accepted count, preview model, real inspection and bilingual export implemented.
- [x] Tasks 3–5: AGENT_TOOL uses same queue/admission/lease/lock; persisted results and owner context; extract/export/burn artifact handoff; six project/job tools and ASR-only Studio tracker added.
- [x] Task 6: validated decisions, bounded inputs/history/time, owned context and terminal job/artifact verification; pending/stale/error outcomes cannot claim success.
- [x] Task 7: real FFmpeg short-media chain, Runner submit/wait/verified render, ownership/recovery/cancel/config/migration tests. Final log review also found socket cancellation interrupting pool return; shielded session cleanup added with a failing-before/passing-after regression.
- [x] Task 8: both OneFL repository skills and UI metadata created; quick_validate passed for both.
- [x] Task 9: 117 backend tests, frontend regression/TypeScript/production build, 84-file Python compile and diff check passed; production browser 22/22 passed after final cleanup fix. Provider/long-media/deployment limits retained in [closure report](/D:/OneFl/docs/reviews/2026-10-21-agent-tool-completion.md).
