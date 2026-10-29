# OneFL

OneFL uploads or downloads video, extracts speech, translates subtitle batches, supports manual review, synthesizes timed dubbing, and burns subtitles with FFmpeg. The current implementation runs media jobs on one host with persistent local storage and SQLite or PostgreSQL metadata.

## Start on Windows

Use Python 3.11 and Node 20. Preserve an existing `.env`; for a new installation copy `.env.example` to `.env` and configure an accessible Gemini or OpenAI model/key. FFmpeg must include libass and libx264; the imageio-ffmpeg binary is a fallback when FFmpeg is absent from PATH.

```powershell
py -3.11 -m venv backend/.venv
backend/.venv/Scripts/python.exe -m pip install -e './backend[dev]'
```

In a separate frontend terminal:

```powershell
Set-Location frontend
npm ci
npm run dev -- --hostname 127.0.0.1
```

From the repository root, start the API:

```powershell
backend/.venv/Scripts/python.exe -m uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8000
```

Open `http://localhost:3000`. Without credentials, development access is restricted to loopback. With `API_ACCESS_TOKEN`, sign in through the login page; the browser receives an HttpOnly session cookie. `AUTH_USERS` optionally maps safe user IDs to separate tokens. Existing projects belong to user `local`; keep a `local` token to retain access.

## Jobs, recovery and files

Pipeline, download, retranslation, dubbing and burn requests persist a job before execution. One project can own one active job; the bounded queue processes one media project at a time, with bounded parallel burn chunks. API processes sharing the database **must also share the same local output and scratch directories**. The worker uses a DB lease plus an OS file lock; this is a single-host deployment.

Jobs persist their input configuration, status, heartbeat and error. After a process restart, interrupted jobs resume through the queue, reusing valid ASR/TTS/render checkpoints. A reset or deletion first requests cancellation and waits for native inference/media processes to stop. HTTP 409 during cancellation means the worker has not acknowledged shutdown yet; retry after it stops. Force ASR replaces transcript cues; force translation preserves manually edited cues. Explicit retranslation of selected cues replaces their edited translations.

Chunk upload uses upload IDs, a chunk manifest, retry checksums and explicit finalization; missing or conflicting chunks fail. The legacy multipart endpoint also validates complete media and invalidates previous transcript/audio/render references. Failed providers and media processes fail the job. The application does not manufacture dialogue, substitute source text as a successful translation, publish silent TTS, or return the source video as a successful render.

Back up the configured database **and** `data` before upgrading. Startup applies introspected migrations to that DSN; unavailable PostgreSQL does not switch to another database. Duplicate cue indices or invalid legacy cue timing stop migration with an actionable error so data can be repaired from a backup. No automatic deletion of conflicting rows is performed.

Timed audio mixing uses fixed PCM blocks on disk. Reserve disk space for the input, extracted audio, synthesis cache, render chunks and final outputs; RAM bounds do not eliminate disk requirements. Every hour, while the durable queue is idle, retention removes expired scratch and unreferenced output files, excluding current DB-referenced artifacts and lock files. The default retention is 14 days. Deleting a project removes its contained media directories.

## Capabilities and deployment

- ASR uses Faster-Whisper, bounded audio chunks and VAD. With diarization disabled, cues retain `SPEAKER_00`; labels are not fabricated by alternation.
- Optional diarization requires `pip install -e './backend[diarization]'`, `HF_TOKEN`, model access and `ENABLE_SPEAKER_DIARIZATION=true`. Its default device is CPU, avoiding automatic simultaneous GPU residency with Whisper. Real model accuracy and cross-chunk speaker identity require validation on representative media.
- `ENABLE_SPEAKER_PROFILER` controls text-based profile inference. `ENABLE_VISUAL_CONTEXT=true` adds bounded real frame samples through a vision-capable configured OpenAI model; this incurs provider requests. Missing configuration fails explicitly.
- Translation providers are Gemini and OpenAI. An explicit model override is honored without changing providers/models. Otherwise an enabled provider fallback uses the configured alternate provider. Guardrail repair has a finite retry budget; unresolved QC fails. Preserved manual edits retain QC warnings.
- Voice catalog entries with legacy `vieneu-*` IDs are Edge voice profiles with rate/pitch/EQ, not a separate VieNeu synthesis server. Preview uses the selected provider/profile and text.
- The default narrator is **Ngọc Huyền** (`DEFAULT_TTS_VOICE=vieneu-ngoc-huyen`). New project/speaker defaults, HTTP/Agent requests and the dubbing dialog use the configured default; an explicitly saved project/dubbing/speaker voice remains selected. Edge TTS requires **7.3.1 or newer** for the current Microsoft handshake. Provider failures keep the chosen voice and show an actionable preview error rather than silently changing providers. Restart the backend after changing its configuration or dependencies, once its active jobs have finished. [Default voice and preview verification](docs/reviews/2026-10-22-ngoc-huyen-default-preview.md).
- The default narrator is **Ngọc Huyền** (`DEFAULT_TTS_VOICE=vieneu-ngoc-huyen`). New project/speaker defaults, HTTP/Agent requests and the dubbing dialog use the configured default; an explicitly saved project/dubbing/speaker voice remains selected. Edge TTS requires **7.3.1 or newer** for the current Microsoft handshake. Provider failures keep the chosen voice and show an actionable preview error rather than silently changing providers. Restart the backend after changing its configuration or dependencies, once its active jobs have finished. [Default voice and preview verification](docs/reviews/2026-10-22-ngoc-huyen-default-preview.md).
- Player color/mask controls preview presentation; the Burn Video dialog defines exported render settings. The player shows all active cues when they overlap, using the same half-open cue intervals as export. Studio marks overlapping cues for review.
- Studio's **Sửa thời gian** action edits start/end seconds with the translated text in one save. Invalid or out-of-video intervals are rejected; failed saves and remote changes retain the draft. Saving invalidates previous dubbing/render references across tabs. Regenerate those outputs after changing timing.
- Newly generated dubbing fits decoded PCM inside each subtitle cue, including the last cue, without borrowing the following gap or cutting the final word. Tempo fitting is bounded to 2.5x; impossible fits fail with the cue index and guidance to shorten text/edit timing. This is a technical limit, not a guarantee of natural speech at high speed.
- **Kiểm tra đồng bộ lồng tiếng** in Studio reads `GET /api/v1/tts/projects/{id}/timing` for the current owned audio. Reports contain per-cue source/fitted duration, audio end, speedup and overlap; the current report survives retention and is invalidated with its audio reference. Older audio needs regeneration to get a report. Timing QC does not score pronunciation, translation meaning or lip-sync. Original-audio mixing lowers the entire original track; it does not separate speech from background music.
- S3/R2/MinIO storage, Temporal orchestration, Redis event transport and a distributed GPU fleet remain architecture targets. Startup currently requires `STORAGE_DRIVER=local`; optional Compose infrastructure profiles do not implement those integrations.

For containers, set a random `API_ACCESS_TOKEN` of at least 24 characters, configure PostgreSQL credentials and run `docker compose up --build`. The frontend is built with the backend's internal DNS address. Published ports bind to loopback; use a trusted HTTPS reverse proxy and set `CORS_ORIGINS` to its browser origin for remote deployment. Production sessions use Secure cookies. URL ingestion is limited to configured video hosts and rejects private/loopback initial destinations; deploy with restricted network egress as well. Docker image execution is not covered by the local Windows test evidence.

## Bilibili URL recovery

The downloader uses yt-dlp 2026.10.21 or newer. When a public Bilibili video page omits embedded `INITIAL_STATE`, a scoped extractor adapter reads its signed WBI View metadata and reuses upstream player/format/multipart logic. It requires successful API metadata for the requested video and preserves explicit access/rate-limit failures. No browser credentials are read. Updating yt-dlp alone does not replace this compatibility fix.

If downloading fails before a local source exists, Studio's pipeline retry queues a DOWNLOAD job before ASR; it does not start ASR against a missing file. URL inspection failures are shown in the creation dialog. If the site denies access, check the same URL in a browser or upload the local video. [Verified Bilibili repair](docs/reviews/2026-10-22-bilibili-ingestion.md) records the exact source, stream checks and limitations.

## White cover bands and reference subtitle style

In **Burn Video**, choose **Áp dụng kiểu mẫu** to use opaque white top/bottom bands and white uppercase bold italic subtitles with a black outline. The `comic` ASS preset uses Arial with horizontal scaling to approximate the supplied reference. Unconfigured projects default to this style; explicit saved settings remain until changed. The preview uses the source video's aspect ratio and the active cue, with a sample sentence between cues. Browser font metrics/line wrapping are approximate; review the rendered MP4 before posting.

The starting bands cover 11% at the top and 15% at the bottom. Adjust **Chiều cao dải trên (%)** (0–28) and **Chiều cao dải dưới (%)** (0–35) to fit the source; zero disables that band. Covers are rendered before ASS and keep the source dimensions/audio. Chinese text or logos outside those bands remain visible. Choose the separate region/OCR cleanup mode below for those areas.

Translated text becomes uppercase only in the `comic` ASS/video presentation; edited text and SRT/VTT retain their saved casing. Completed-render and Studio ASS downloads use the saved preset. The player menu changes preview only; the Burn dialog saves the output configuration. [Style verification and short 1080p sample](docs/reviews/2026-10-22-whitebars-comic-style.md).

## White cover bands and reference subtitle style

In **Burn Video**, choose **Áp dụng kiểu mẫu** to use opaque white top/bottom bands and white uppercase bold italic subtitles with a black outline. The `comic` ASS preset uses Arial with horizontal scaling to approximate the supplied reference. Unconfigured projects default to this style; explicit saved settings remain until changed. The preview uses the source video's aspect ratio and the active cue, with a sample sentence between cues. Browser font metrics/line wrapping are approximate; review the rendered MP4 before posting.

The starting bands cover 11% at the top and 15% at the bottom. Adjust **Chiều cao dải trên (%)** (0–28) and **Chiều cao dải dưới (%)** (0–35) to fit the source; zero disables that band. Covers are rendered before ASS and keep the source dimensions/audio. Chinese text or logos outside those bands remain visible. Choose the separate region/OCR cleanup mode below for those areas.

Translated text becomes uppercase only in the `comic` ASS/video presentation; edited text and SRT/VTT retain their saved casing. Completed-render and Studio ASS downloads use the saved preset. The player menu changes preview only; the Burn dialog saves the output configuration. [Style verification and short 1080p sample](docs/reviews/2026-10-22-whitebars-comic-style.md).

## Remove source Chinese text and logos

Install the optional local cleanup engine and explicitly prepare its bundled OCR models from the repository root:

```powershell
backend/.venv/Scripts/python.exe -m pip install -e './backend[cleanup]'
backend/.venv/Scripts/python.exe scripts/prepare_video_cleanup.py
```

Restart the backend after installation. In **Burn Video**, choose **Xóa chữ/logo — phục hồi nền**. Automatic OCR targets Chinese text. Select additional image logos on the source video, or enter normalized coordinates as percentages; enable **Bám theo logo di chuyển** and select a clear reference time for moving logos. Saved regions/OCR settings belong to the project and are reused when reopening render settings. Removal runs before translated ASS, preserving the new Vietnamese subtitles. Completed renders expose processing counts and tracking misses through **Kết quả xóa chữ/logo** and `GET /api/v1/projects/{id}/pipeline/cleanup-report`.

This is CPU OCR plus OpenCV Telea inpainting, which reconstructs pixels from surrounding image areas. It is not a generative video restoration model: detailed backgrounds can smear/flicker, stylized Chinese or text appearing between scans may be missed, and non-text logos need manual selection. Shorter OCR intervals cost more CPU. A tracking miss leaves uncertain pixels for review; zero misses does not certify complete removal. Supported inputs are SDR 8-bit up to 4K/120fps; HDR/10-bit fails explicitly rather than being silently flattened. Source resolution is retained, without automatic 1080p upscaling. Frames stream through bounded pipes with one cleanup worker; full 10-hour resource usage/drift is not yet benchmarked.

Models stay under `data/models/video_cleanup` with a SHA-256 manifest. Missing dependencies/models fail before a BURN job is queued; no models are silently downloaded during rendering. Existing cover/blur/crop modes remain available. Container builds may enable dependencies with `--build-arg INSTALL_CLEANUP=true` (backend build context), then explicitly run `python -m app.services.cleanup_ocr` with persistent `/app/data` mounted before rendering. Container execution is not certified by Windows tests.

[Cleanup verification and usage](docs/reviews/2026-10-22-video-text-logo-cleanup.md) records actual short media, OCR and browser evidence.

## Verification

Tests use a disposable DSN; never point the test suite at your working database.

```powershell
$env:DATABASE_URL='sqlite+aiosqlite:///:memory:'
backend/.venv/Scripts/python.exe -m pytest tests -q -p no:cacheprovider --basetemp=tmp/verification
backend/.venv/Scripts/python.exe scripts/eval_golden_dataset.py
```

In `frontend`, run `npm test`, `npx tsc --noEmit --incremental false`, and `npm run build`. Regression tests include injected provider/process failures, isolated migrations and ownership, durable job admission/recovery/cancellation, upload retries, PCM overlap, and short real FFmpeg burn/mux/filter cases. Fixtures contain 15 independent reference dialogues and 290 deduplicated glossary entries. Five reference dialogues deliberately exceed CPS and must be rejected. These checks do not measure live translation semantics or prove operation on a 10-hour/50-GB input.

See [the remediation record](docs/reviews/2026-10-21-remediation-results.md), [architecture](Architecture.md), and [translation specification](Translation_Engine_Specification.md). Historical audit probes assert pre-fix bugs; use `tests` for current acceptance.

## Isolated browser verification

The [feature/UI/backend verification record](docs/reviews/2026-10-21-feature-ui-backend-verification.md) contains browser scenarios and screenshots. The fixture substitutes only external ASR/LLM/TTS/URL providers; authentication, API, SQL, job queue, WebSocket and short FFmpeg media operations run normally. It uses its own database and files under `tmp/feature-audit/runtime`. Do not deploy the fixture as the application or use its test token for normal access.

From the repository root, install browser tooling separately from application dependencies:

```powershell
npm.cmd install --prefix tmp/feature-audit/tools --no-save --package-lock=false --ignore-scripts playwright@1.58.2
tmp/feature-audit/tools/node_modules/.bin/playwright.cmd install chromium
```

Use three terminals, with ports 8100 and 3100 available. Terminal 1 starts the isolated backend:

```powershell
backend/.venv/Scripts/python.exe tests/e2e_backend.py
```

Terminal 2 starts a frontend using the fixture API:

```powershell
$env:BACKEND_INTERNAL_URL='http://127.0.0.1:8100'
Set-Location frontend
node node_modules/next/dist/bin/next dev -p 3100 --hostname 127.0.0.1
```

Terminal 3 runs the browser scenarios:

```powershell
$env:NODE_PATH=(Resolve-Path tmp/feature-audit/tools/node_modules).Path
$env:ONEFL_E2E='1'
node frontend/tests/browser-flow.cjs
```

Expect `BROWSER SCENARIOS 25`, exit 0, and `errors: []` / `networkErrors: []` in `tmp/feature-audit/browser-results.json`. Scenarios include cue timing validation/save/draft conflicts, overlapping preview and current dubbing QC. `ONEFL_BROWSER` optionally selects a Chromium executable. Traces/screenshots are written to `tmp/feature-audit`; trace archives can be large. Stop both fixture servers after testing. A forced backend restart may wait up to the worker lease timeout before jobs resume.

To check a production build, build with the chosen fixture address and serve it on port 3100 instead of the dev server. The final recorded run used a build targeting port 8000, an isolated backend with `ONEFL_E2E_PORT=8000`, and the browser runner with `ONEFL_FIXTURE_URL=http://127.0.0.1:8000`. Use port 8000 only when it is free; never replace a running application. After a custom test build, rebuild with the normal `BACKEND_INTERNAL_URL` before ordinary use.

## Agent tools and project skills

The Agent toolkit exposes 16 tools through discovery, execute-tool and chat APIs. Media ASR/burn operations return durable job IDs; use get_job_status/wait_for_job instead of treating queue admission as completion. Project/job tools share HTTP ownership checks and worker lifecycle. Runner results distinguish COMPLETED, PENDING and FAILED and can verify a required artifact in project context.

See [tool catalog and client migration](docs/agent-tools.md) and [completion evidence](docs/reviews/2026-10-21-agent-tool-completion.md). ASR can extract source audio; project export writes a versioned subtitle artifact; burn consumes ASS. Choose style presets during export, not through the burn-file tool. Back up DB/media before startup adds the nullable jobs.result column.

Repository skills [onefl-agent-tools](.agents/skills/onefl-agent-tools/SKILL.md) and [onefl-media-verification](.agents/skills/onefl-media-verification/SKILL.md) capture the project-specific contracts and safe isolated checks. They do not introduce external services or provider credentials.

## Performance verification

See [measured flow/performance results](docs/reviews/2026-10-21-flow-performance.md). Worker completion now wakes scheduling immediately; local enqueue has a wakeup signal and other producers retain DB polling. Metadata probes use a bounded 512-entry file-stat cache, with stream validation and invalidation on file change. TTS creates a bounded worker pool (`TTS_MAX_CONCURRENCY=8`, configurable 1–32) instead of one task per cue. Studio coalesces refresh bursts while preserving a trailing refresh for changes during a fetch.

Run `backend/.venv/Scripts/python.exe scripts/benchmark_flow.py --label after` for isolated scheduler/real metadata measurements. For the production Studio fixture, set the browser-test environment described above and run `node frontend/tests/performance.cjs after`; it seeds 1,000 cues in a disposable project. Reports are written under `tmp/performance`. These measurements do not benchmark live AI/model/GPU throughput. Lifecycle tests use temporary file SQLite so concurrent API and worker sessions have independent connections; single-session unit fixtures may use SQLite memory.
