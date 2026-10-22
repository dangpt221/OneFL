# Feature/UI/backend verification

## Goal and constraints

Verify user-facing features against actual API/job/WebSocket behavior, fix reproduced UI/backend contract defects, and report requirement coverage with evidence. Preserve user edits and live data. Use isolated storage/database and separate ports for browser checks. No live AI charges, model downloads, production migration or real-project mutation.

## File impact and atomic tasks

| Step | Target files and action | Verification / expected result |
|---|---|---|
| 1 | Read `frontend/src/lib/api.ts`, route handlers, all pages/modals; map create/upload, pipeline/review, speaker/glossary, dub/burn, settings/auth flows | Write requirement/contract matrix, identify real mismatches |
| 2 | Prepare temporary browser tools and isolated backend/frontend on unused ports; probe health/session | Both endpoints return expected responses; no live DB access |
| 3 | Exercise dashboard/CreateProjectModal in a browser: login, upload, queued/running/failure, polling/filter | No page error; UI reflects API state without reload |
| 4 | Exercise Studio/SubtitleEditor and API: edit, selected retranslate, exports, overlapping cues, reconnect | Data persists and other sessions synchronize; valid exports |
| 5 | Exercise SpeakerMatrixModal/GlossaryModal CRUD/import/presets and error handling | UI edits match API/export and remain consistent after reopening |
| 6 | Exercise DubbingModal/BurnProgressModal/VideoPlayer: configuration, preview, queue/failed/success states, downloads | Output and selected settings correspond to latest backend version |
| 7 | Add focused regressions for observed defects under `tests` / `frontend/tests`; modify only affected routes/components/helpers | Demonstrate failing case, fix root cause, repeat targeted check |
| 8 | Verify desktop/mobile layouts and browser console/network/WebSocket after fixes; capture screenshots | No clipped essential controls, unexpected errors or stale state |
| 9 | Run isolated pytest, frontend regression/TypeScript/build after final changes | All checks pass, retain output evidence |
| 10 | Write `docs/reviews/2026-10-21-feature-ui-backend-verification.md` and update session ledger | Each feature has observed status and explicit limits |

Review checkpoints are progress updates; the user already authorized fixing defects and requested this verification. Continue without a new approval gate. If browser tooling needs network or process privileges, use the actual sandbox escalation mechanism; do not claim browser coverage without a successful run. Mock only external AI/URL providers in the isolated harness and label that scope clearly. A UI test with mocked external providers does not demonstrate model quality or 10h/50GB performance.

## Execution record

- [x] Steps 1–2: traced feature/API/job/WS contracts, provisioned isolated Playwright tooling and fixture media/database.
- [x] Steps 3–6: exercised auth/upload/pipeline/review, cross-tab subtitle/speaker/glossary, exports, dubbing, burn/rerender, queue, settings, reconnect/failure/delete.
- [x] Step 7: fixed reproduced defects; added content revision and atomic mutation/job admission guards, heartbeat deletion regression, preview model/cache and frontend playback/workflow/modal regressions.
- [x] Step 8: desktop/mobile checks and screenshots, real video playback, no browser pageerror or unexpected requestfailed.
- [x] Step 9: 97 backend tests passed; frontend regressions, TypeScript, production build passed; 80 app/test Python files compiled; diff whitespace check passed. Final 20-scenario browser run used the production build after the worker fix.
- [x] Step 10: [feature matrix and evidence](/D:/OneFl/docs/reviews/2026-10-21-feature-ui-backend-verification.md), README reproduction instructions and session ledger updated.

External-provider boundaries use fixtures. Real AI/model/URL quality, PostgreSQL/Docker/HTTPS deployment and 10h/50GB load remain explicitly unverified; the report does not equate short synthetic media with those requirements.

## Execution record

- [x] Steps 1–2: traced feature/API/job/WS contracts, provisioned isolated Playwright tooling and fixture media/database.
- [x] Steps 3–6: exercised auth/upload/pipeline/review, cross-tab subtitle/speaker/glossary, exports, dubbing, burn/rerender, queue, settings, reconnect/failure/delete.
- [x] Step 7: fixed reproduced defects; added content revision and atomic mutation/job admission guards, heartbeat deletion regression, preview model/cache and frontend playback/workflow/modal regressions.
- [x] Step 8: desktop/mobile checks and screenshots, real video playback, no browser pageerror or unexpected requestfailed.
- [x] Step 9: 97 backend tests passed; frontend regressions, TypeScript, production build passed; 80 app/test Python files compiled; diff whitespace check passed. Final 20-scenario browser run used the production build after the worker fix.
- [x] Step 10: [feature matrix and evidence](/D:/OneFl/docs/reviews/2026-10-21-feature-ui-backend-verification.md), README reproduction instructions and session ledger updated.

External-provider boundaries use fixtures. Real AI/model/URL quality, PostgreSQL/Docker/HTTPS deployment and 10h/50GB load remain explicitly unverified; the report does not equate short synthetic media with those requirements.
