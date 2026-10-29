# Resume dubbing conflict fix plan

**Goal:** Fix the reported 409 without bypassing durable job admission. Active dubbing resumes are idempotent; Studio offers resume only for interrupted dubbing with saved configuration.

**Evidence:** User confirmed `Project already has an active job`. Tracker currently exposes both resume buttons for all processing states, including QUEUED and active DUBBING, so it requests a second enqueue. The supplied live ID is unavailable from the currently reachable API (404); a read-only legacy root SQLite row exists, but its schema differs from the running API. Do not mutate/reset that project or infer live job health from the legacy row.

**Architecture & constraints:** Keep one job per project, existing lease/recovery/ownership and provider/cache behavior. No DB migration, video processing or GPU concurrency change. Do not restart the user's servers on 3000/8000; use disposable SQLite and separate fixture ports. No live project writes/provider calls.

## File impact

| Action | File |
| --- | --- |
| Modify | [resume API](/D:/OneFl/backend/app/api/v1/projects.py:391), return existing matching job; re-read after admission race |
| Modify | [project view policy](/D:/OneFl/frontend/src/lib/projectView.ts:1), recovery eligibility |
| Modify | [tracker](/D:/OneFl/frontend/src/components/PipelineProgressTracker.tsx:380), gate actions, preflight refresh, guard duplicate clicks, inline error |
| Test | [backend regressions](/D:/OneFl/tests/test_resume_dubbing.py), [frontend regressions](/D:/OneFl/frontend/tests/regressions.cjs:120), [browser regression](/D:/OneFl/frontend/tests/resume-dubbing.cjs) |
| Docs | [results](/D:/OneFl/docs/reviews/2026-10-22-resume-dubbing-conflict.md), [ledger](/D:/OneFl/.agents/SESSION_STATE.md:1) |

## Atomic tasks

1. Add isolated tests: queued/running DUBBING returns same job/count; idle failed dubbing queues once; conflicting kind/cancellation/orphan still 409; no saved config still fails; simulate a concurrent winning enqueue. Command `$env:DATABASE_URL='sqlite+aiosqlite:///:memory:'; backend/.venv/Scripts/python.exe -m pytest tests/test_resume_dubbing.py -q -p no:cacheprovider --basetemp=tmp/resume-dubbing-fix/red`. Expect failures on repeated resume before fix.
2. Add actual React SSR assertions for no resume buttons on active/queued/translation/created projects; failed/cancelled saved dubbing exposes resume, missing config gives configuration guidance. `npm.cmd test` must fail first.
3. Update `resume_project_dubbing(...) -> dict` using current project/job read. Return `already_active=true` only for the same DUBBING job in QUEUED/RUNNING and not cancelling. Preserve 409 for another operation or inconsistent ownership, and re-read after an enqueue 409 to handle a racing resume. Run focused pytest; expect pass, one stored job.
4. Add `getDubbingRecovery(project)` policy; use it in both tracker action locations. Synchronously guard click submission with a ref; GET latest project before POST, refresh if a job already exists, show meaningful inline errors and refresh state after errors. Generic retry must not start the translation pipeline for a failed dub. Run frontend regression and TypeScript; expect pass.
5. Build using separate fixture ports and run browser scenarios for active-job hiding, interrupted resume, duplicate requests returning same job, race preflight, inline failure and correct workflow. Run full backend suite and compile changed Python. Restore normal frontend build after fixture verification; never replace the running user's servers. Record evidence and stop owned fixture helpers using netstat/sockets.

## Checkpoint/fallback

The user's bug report authorizes the reversible fix and regression checks. Keep the live job running; do not clear active_job_id or change DB rows to make 409 disappear. If a different operation owns the project, return actionable conflict and keep its lock. Natural TTS/model/media quality is outside these contract tests.
