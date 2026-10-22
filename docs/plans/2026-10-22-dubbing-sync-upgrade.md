# Dubbing synchronization upgrade implementation plan

**Goal:** Fix DS01–DS03 from the readiness review: speech fits its own subtitle interval, all overlapping cues appear in preview, and Studio edits cue timing. Expose measured timing QC without claiming language/voice accuracy.

**Architecture & Constraints:** Keep the existing durable job, ownership, artifact invalidation and WebSocket flow. Fit decoded 24-kHz PCM to each cue interval without truncating words; bounded tempo correction, max 2.5x, fail explicitly when impossible. Disk blocks/worker limits remain suitable for long media; no whole-video RAM load or GPU/model changes. Store QC beside each versioned dubbed audio, read only through the current owned project reference. No DB migration, live providers or vocal-separation dependency.

**Skills:** writing-plans, executing-plans, test-driven-development, clean-code, fastapi-pro, nextjs-best-practices, onefl-media-verification, verification-before-completion.

## File impact matrix

| Action | File / scope |
| --- | --- |
| Modify | [TTS service](/D:/OneFl/backend/app/services/tts_service.py:457), decoded PCM fit and timing report |
| Modify | [TTS API](/D:/OneFl/backend/app/api/v1/tts.py:248), owned timing report endpoint; [schemas](/D:/OneFl/backend/app/schemas/tts.py:1) |
| Modify | [subtitle API](/D:/OneFl/backend/app/api/v1/subtitles.py:194), reject edits outside source duration |
| Modify | [timeline](/D:/OneFl/frontend/src/lib/subtitleTimeline.ts:1), [player](/D:/OneFl/frontend/src/components/VideoPlayer.tsx:82), all-active preview |
| Modify | [editor](/D:/OneFl/frontend/src/components/SubtitleEditor.tsx:70), timing drafts, validation, overlap warning |
| Create | [quality summary](/D:/OneFl/frontend/src/components/DubbingQualitySummary.tsx), typed report display |
| Modify | [API client](/D:/OneFl/frontend/src/lib/api.ts:1), [Studio](/D:/OneFl/frontend/src/app/projects/[id]/page.tsx:590), quality display/editor duration |
| Test | [sync regressions](/D:/OneFl/tests/test_dubbing_sync.py), [frontend regressions](/D:/OneFl/frontend/tests/regressions.cjs:85), [browser flow](/D:/OneFl/frontend/tests/browser-flow.cjs:45) |
| Docs | [README](/D:/OneFl/README.md:42), [completion report](/D:/OneFl/docs/reviews/2026-10-22-dubbing-sync-upgrade.md), [ledger](/D:/OneFl/.agents/SESSION_STATE.md:1) |

## Atomic tasks (2–5 minutes each)

1. Write real-FFmpeg speech gap/last-cue regressions, tempo overflow rejection and report assertions in `tests/test_dubbing_sync.py`. Generate local tones only; decode PCM and measure 25-ms windows. Run isolated pytest; expected fail on observed end overrun.
2. Write frontend assertions for an all-active indexed query (half-open intervals, unordered/tied cues), plus timing validation/draft persistence browser scenarios. Run `npm.cmd test`; expected fail for missing all-active index.
3. In `TTSService.dub_project_timeline(...) -> Path`, decode cached speech first, measure samples, fit within `[start,end)` using at most three tempo attempts and cumulative <=2.5 factor; reject remaining overflow, never trim speech. Preserve sample offsets and block mixer. Store successful per-cue `source_duration`, `fitted_duration`, `speedup`, `audio_end`, overlap indication beside output. Run sync tests; expected pass.
4. Add Pydantic timing report models and GET `/tts/projects/{project_id}/timing`. Resolve only current project audio within its storage directory, read in thread, validate JSON; missing legacy report 404, corrupt report explicit server error. Add owner/missing/stale/invalid report tests; isolated pytest must pass.
5. Extend timeline index with all-active retrieval in start order; retain latest-cue wrapper for existing callers. Player renders all active translated lines; editor uses half-open active intervals and overlap warnings. `npm.cmd test` and TypeScript must pass.
6. Add editable seconds fields to the existing cue draft, validate finite `0 <= start < end <= duration`, retain draft on HTTP error, save text/timing atomically using existing update endpoint. Pause auto-follow while editing. Backend enforces duration too. Add API regression and browser invalid/edit/error/two-tab/invalidation cases; expect clear validation and persisted matching times.
7. Render timing report summary from typed client/component after dubbed artifact changes, including max speedup, overlap and semantic-quality limitation. Stale requests must not replace current state; 404 legacy reports handled explicitly. Compile/type checks and browser dubbing scenario verify report appears.
8. Run full isolated backend suite, frontend regressions/TypeScript/build, then production Chromium fixture scenarios. Verify no unexpected page/network/server errors; stop only owned helpers. Save results and document unverified real AI/long-media/device quality. Compile changed Python and run whitespace checks.

Verification commands from root (PowerShell):

```powershell
$env:DATABASE_URL='sqlite+aiosqlite:///:memory:'
backend/.venv/Scripts/python.exe -m pytest tests/test_dubbing_sync.py -q -p no:cacheprovider --basetemp=tmp/dubbing-upgrade/focused
backend/.venv/Scripts/python.exe -m pytest tests -q -p no:cacheprovider --basetemp=tmp/dubbing-upgrade/full --junitxml=tmp/dubbing-upgrade/pytest-results.xml
```

Frontend directory: `npm.cmd test`; `node node_modules/typescript/bin/tsc --noEmit --incremental false`; `npm.cmd run build`. Expected exit 0. Browser fixture instructions are in README; do not replace occupied application ports.

## Checkpoint & fallback

Final verification exposed an existing scheduler-test fixture failure under load: cancellation invalidated the single SQLite :memory: connection, and worker shutdown then saw no worker_leases table. Add a temporary file-backed `worker_db` fixture in [performance tests](/D:/OneFl/tests/test_performance_contracts.py:12) for tests starting/cancelling the scheduler. Keep production DB/worker behavior unchanged. Verification: rerun the seven performance contracts and full suite with zero failures.

User's instruction to fix/upgrade approves executing the measured findings in this plan. Continue reversible implementation and checks without another approval step. Review after focused tests before full integration. Keep long-media and natural-language claims separate. Preserve existing dirty changes, normal DSN and `.env`; no commits/pushes. If a new fit cannot satisfy timing, fail that job with cue ID and guidance rather than publish truncated speech. Existing audio has no new report until regenerated.
