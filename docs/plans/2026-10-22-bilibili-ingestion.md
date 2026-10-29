# Bilibili ingestion repair implementation plan

**Goal:** Recover public Bilibili extraction when HTML initial state is absent but its signed metadata API succeeds, surface actionable failures and retry the correct durable job.

**Architecture & Constraints:** Old 2026.08.19 and new 2026.10.21 both fail on BV1MHh66uEFH; unsigned metadata API returns HTTP 412 and HTML has no INITIAL_STATE. User confirms public browser playback. Further probe proves the existing signed WBI detail endpoint returns code 0, matching bvid/cid, 17551 seconds and download=1: upstream only checks this response for Bangumi redirects and discards valid ordinary metadata. Add a narrowly scoped yt-dlp extractor adapter mapping that real metadata into its existing initial-state schema, then reuse upstream format/subtitle/multipart handling. Respect explicit risk/auth/denial responses; no access bypass or invented media. Preserve URL validation, ownership, cancellation, concurrency/format limits. No cookie handling, live full-video download, AI invocation or database migration.

**Tech Stack:** FastAPI/async SQLAlchemy, yt-dlp, Pydantic settings, Next.js/React/TypeScript.

## File impact matrix

| Action | File | Purpose |
| --- | --- | --- |
| Create | [extractor adapter](/D:/OneFl/backend/app/services/bilibili_extractor.py:1) | Validated signed-metadata fallback, reuse upstream extractor |
| Modify | [downloader](/D:/OneFl/backend/app/services/video_downloader.py:15) | Register adapter for Bilibili only, same inspect/download error classification and exact platform detection |
| Modify | [pipeline router](/D:/OneFl/backend/app/api/v1/pipeline.py:17), [ingestion](/D:/OneFl/backend/app/services/ingestion_service.py:11) | Retry failed URL downloads as DOWNLOAD jobs; preserve force_reprocess |
| Modify | [pyproject](/D:/OneFl/backend/pyproject.toml:26), [requirements](/D:/OneFl/backend/requirements.txt:20) | Verified yt-dlp minimum 2026.10.21 |
| Modify | [create modal](/D:/OneFl/frontend/src/components/CreateProjectModal.tsx:50) | Display inspection errors; prevent stale metadata/response updates |
| Create | [tests](/D:/OneFl/tests/test_video_downloader.py:1) | Adapter fallback/denial/normal-page/multipart, extraction failure mapping, success/cancellation and retry contracts |
| Create | [browser test](/D:/OneFl/frontend/tests/bilibili-errors.cjs:1) | Actual modal inspection-error visibility and stale URL behavior |
| Create / Modify | [unit UI test](/D:/OneFl/frontend/tests/url-inspection-regressions.cjs:1), [package](/D:/OneFl/frontend/package.json:10) | Include inspection handler regression in npm test |
| Modify | [runtime test](/D:/OneFl/tests/test_runtime_integration.py:1) | Failure release and re-download rather than missing-source pipeline |
| Modify | [README](/D:/OneFl/README.md:57), [state](/D:/OneFl/.agents/SESSION_STATE.md:1) | Operator setup, evidence, honest source-access limitation |

## Atomic tasks (2–5 minutes each)

1. Write failing isolated downloader/adapter tests (`tests/test_video_downloader.py:1-220`). Fake network edges only. Cover missing HTML state + successful signed metadata, existing HTML unchanged, risk/denied/mismatched metadata, AV/BV identifiers and multipart page retention; known INITIAL_STATE/412/login errors use stable codes and actionable text. Run `backend/.venv/Scripts/python.exe -m pytest tests/test_video_downloader.py -q -p no:cacheprovider --basetemp=tmp/bilibili-tests`; expect red on baseline.
2. Implement `BilibiliInitialStateIE` in `bilibili_extractor.py:1-100`, replacing only the BiliBili extractor registry key. Override webpage handling to append a validated initial-state schema derived from signed WBI View/owner/tags only when ordinary HTML lacks it; delegate existing state, risk challenges and Bangumi redirects to upstream. Preserve page query and reject denial/mismatched bvid/missing cid. Verify tests plus real metadata-only extraction of exact user URL; expect correct id/duration and playable formats without cookies.
3. Register adapter for Bilibili only; add `VideoDownloadError(code,message)` conversion in `video_downloader.py:15-120,210-240`. Metadata keeps success:false and adds error_code; download raises same message with original diagnostic cause. Cancellation remains unwrapped. Detect platform by parsed hostname. Repeat focused tests, expect pass.
4. Add retry tests and minimal router/service change (`pipeline.py:17-35`, `ingestion_service.py:11-50`). For source URL with no local media and restart from ingestion, enqueue DOWNLOAD with URL/auto_start/force_reprocess; later-stage retries without source fail clearly. Existing local-file pipeline stays PIPELINE. Verify focused tests plus `tests/test_runtime_integration.py`, expect durable job ownership and failure release intact.
5. Fix modal inspection handler (`CreateProjectModal.tsx:50-90,210-270`) to show success:false error and preserve only current request's metadata/error/loading. On URL edit invalidate old request and preview. Browser acceptance covers HTTP-200 failure body, transport failure, stale success/failure, changing source tab. Run `npm.cmd test` and `tsc --noEmit --incremental false`, expect exit 0.
6. Raise matching yt-dlp minimum to 2026.10.21 in both dependency manifests; install verified version into the existing venv only after backups/idle-job check. Full backend pytest with disposable DSN, isolated frontend build/browser and log inspection; expect all applicable tests pass. Source extraction may remain blocked externally; preserve failed state and original URL.
7. Restart only verified-idle backend to load changed code/package, check health and read-only endpoint behavior. Preserve user projects/media/.env and frontend. Stop owned fixtures and publish evidence; only metadata/format and optionally bounded short stream checks, no automatic full 4.9-hour live retry/download.

## Review checkpoint & fallback

User authorized fixes and confirms public browser playback. Proceed with reversible edits and isolated validation. No browser credentials required or accessed. If API/player denies access, retain explicit failure and local-file route; never fabricate download success. Target API behavior is verified before implementing compatibility adaptation.
