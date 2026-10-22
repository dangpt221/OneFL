# Flow and Performance Verification Plan

**Goal:** Complete and verify the supported single-host flows, remove measured latency/resource waste, and publish reproducible before/after evidence without claiming live AI or long-video performance.

**Architecture & constraints:** Preserve DB admission/lease/OS lock, cancellation, ownership, translation context/QC and model defaults. Do not parallelize context-dependent translation batches or increase GPU concurrency speculatively. Benchmarks use isolated SQLite/storage, short real media, synthetic provider work and Chromium against a production build. No live database/project/provider access.

## File impact matrix and atomic tasks

| Task | Exact target and change | Verification / expected result |
|---|---|---|
| 1 | Create `scripts/benchmark_flow.py`; measure real worker scheduling and repeated FFmpeg probes with controlled inputs | Save `tmp/performance/before.json` before implementation; record exact workload/settings |
| 2 | Create `tests/test_performance_contracts.py`; reproduce delayed completion pickup and repeated identical probe subprocesses | Targeted pytest fails for intended reason before fixes |
| 3 | Modify [job_service.py](/D:/OneFl/backend/app/services/job_service.py:185): wait on task completion with heartbeat timeout, immediate next queued dispatch and local enqueue wakeup with cross-process polling fallback | No duplicate execution, leases/cancel/recovery still pass; benchmark reduced scheduler overhead |
| 4 | Modify [media_process.py](/D:/OneFl/backend/app/services/media_process.py:45): bounded per-loop metadata cache keyed by file identity/stat, stream validation and coalesced identical probes | Changed/corrupt/strict-stream checks remain effective; repeated same file avoids subprocess |
| 5 | Modify [tts_service.py](/D:/OneFl/backend/app/services/tts_service.py:479): bounded worker tasks instead of one task per cue; keep cache/timing/mixer behavior | Large synthetic cue test bounds scheduled task count; existing real audio/timeline tests pass |
| 6 | Create `frontend/src/lib/refreshCoordinator.ts`; update [Studio](/D:/OneFl/frontend/src/app/projects/[id]/page.tsx:58) to coalesce refresh bursts and retain trailing refresh after in-flight edits | Frontend async regressions prove burst coalescing, trailing refresh and teardown; browser cross-tab/reconnect still passes |
| 7 | Capture baseline/final browser initial Studio requests and timing on same isolated fixture/production build | Count resource calls and report timings without mislabeling as live AI/production RUM |
| 8 | Rerun benchmark, full pytest, frontend regression/TypeScript/build and 22 browser scenarios; inspect logs | All checks pass; compare same workload/settings, report actual limits |
| 9 | Publish `docs/reviews/2026-10-21-flow-performance.md`, update README/ledger and stop owned fixture helpers | Concrete matrix of flows, measured gains and unverified scale/provider/deployment work |

Backend checks: `$env:DATABASE_URL='sqlite+aiosqlite:///:memory:'; backend/.venv/Scripts/python.exe -m pytest ... -p no:cacheprovider --basetemp=tmp/performance-tests-*`. Frontend: `npm.cmd --prefix frontend test`, `frontend/node_modules/.bin/tsc.cmd --project frontend/tsconfig.json --noEmit --incremental false`, build in frontend with normal backend URL. Expected exit 0 with recorded counts; no skipped failures disguised as completion.

**Checkpoint/fallback:** User authorized implementation and optimization. Use progress updates; preserve all prior/user changes. If a proposed optimization changes correctness or cannot demonstrate a benefit, keep existing semantics and record the limit. Real ASR/translation/voice quality, NVENC and 10h/50GB throughput need representative media/provider/GPU evidence and are not inferred from synthetic tasks.

## Execution record

- [x] Baseline scripts and initial failing tests reproduced fixed-sleep scheduling, duplicate probes and task-per-cue fanout.
- [x] Completion-aware scheduling/local wakeup with cross-producer fallback; bounded metadata LRU/same-file locking; TTS bounded worker pool implemented and verified.
- [x] Refresh coordinator preserves trailing invalidation and teardown; initial production Studio GETs reduced from 12 to 4 on the same 1000-cue fixture workload. Median readiness did not improve; report states this explicitly.
- [x] Final backend suite: 124 passed; frontend regression/TypeScript/build passed; 22 production browser scenarios passed; 86 Python files compiled, diff check passed.
- [x] Concurrent API+worker integration tests use temporary file SQLite, replacing inappropriate shared-connection memory pooling for those tests. No application DSN fallback or live DB writes.
- [x] [Results and flow coverage](/D:/OneFl/docs/reviews/2026-10-21-flow-performance.md), README and session ledger updated with measured gains and explicit limits.
