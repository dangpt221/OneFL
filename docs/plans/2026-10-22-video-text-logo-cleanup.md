# Video text/logo removal implementation plan

**Goal:** Add genuine pixel removal before Vietnamese subtitle burn: automatic Chinese-text OCR, selected logo masks with optional tracking, and local background inpainting. Preserve the current lightweight covering modes.

**Architecture:** Router -> validated cleanup configuration in existing BURN job -> bounded streaming cleanup service -> FFmpeg subtitle burn/encode -> existing checkpoint/concat and owned output. OCR uses local CPU ONNX models; OpenCV inpainting fills masked pixels from neighboring content. It is not generative temporal reconstruction or a promise to remove every possible logo perfectly.

**Tech Stack:** FastAPI/Pydantic V2, existing asyncio worker, FFmpeg, OpenCV headless, RapidOCR/ONNX Runtime, React/TypeScript.

## Understanding and decisions

- User explicitly requests implementing the previously described missing removal feature; proceed within that authorization, without another approval gate.
- Machine has RTX 2050 4 GB, no Torch/OpenCV/OCR package; ONNX Runtime/Numpy/PyAV exist. Choose CPU OCR and spatial inpainting, rather than a multi-GB generative video model competing with ASR/render VRAM.
- Automatically target recognized Chinese text; non-text/Latin logos can be selected in the video editor. Tracking handles movement where visual matching remains reliable. Low-confidence tracking is reported, not disguised as successful removal.
- Preserve audio, dimensions and timing; decode/encode with bounded pipes and frame-by-frame memory, no whole-video frame arrays. At most one cleanup render at a time in addition to existing burn admission; video length 10 h/50 GB stays a design constraint, not an unmeasured performance claim.
- Models are prepared explicitly under data/models and checked locally before a job; no credential/browser-profile access or downloads hidden inside production jobs.
- No ASR/diarization configuration change, full user video job, external publishing or source media overwrite. Existing .env and live data remain intact.

## File impact matrix

| Action | Target | Purpose |
| --- | --- | --- |
| Create | [cleanup schema](/D:/OneFl/backend/app/schemas/video_cleanup.py:1) | Normalized regions, tracking/reference time, OCR controls and geometry limits |
| Modify | [burn schema](/D:/OneFl/backend/app/schemas/translation.py:41) | inpaint mode and nested cleanup options |
| Create | [OCR adapter](/D:/OneFl/backend/app/services/cleanup_ocr.py:1) | Local validated models, CJK boxes and CPU resource settings |
| Create | [cleanup service](/D:/OneFl/backend/app/services/video_cleanup.py:1) | Per-frame masks/tracking/inpainting and cancellable FFmpeg streaming |
| Modify | [burner](/D:/OneFl/backend/app/services/video_burner.py:108), [workflow](/D:/OneFl/backend/app/services/workflow_engine.py:393) | Run removal before ASS, keep job/checkpoint/signature contracts |
| Modify | [pipeline API](/D:/OneFl/backend/app/api/v1/pipeline.py:43) | Validate/preflight requested cleanup before enqueue |
| Create | [setup script](/D:/OneFl/scripts/prepare_video_cleanup.py:1) | Prepare small local OCR models and manifest explicitly |
| Modify | [dependencies](/D:/OneFl/backend/pyproject.toml:33), [Dockerfile](/D:/OneFl/backend/Dockerfile:1) | Optional cleanup extra and documented install |
| Create | [region editor](/D:/OneFl/frontend/src/components/VideoCleanupEditor.tsx:1) | Select, review, delete and track logo masks on video |
| Modify | [types](/D:/OneFl/frontend/src/lib/types.ts:1), [api](/D:/OneFl/frontend/src/lib/api.ts:375), [burn modal](/D:/OneFl/frontend/src/components/BurnProgressModal.tsx:1), [Studio](/D:/OneFl/frontend/src/app/projects/[id]/page.tsx:196) | Typed config, OCR controls, saved settings and readable limitations |
| Create | [backend tests](/D:/OneFl/tests/test_video_cleanup.py:1), [frontend tests](/D:/OneFl/frontend/tests/cleanup-regressions.cjs:1), [browser test](/D:/OneFl/frontend/tests/cleanup-browser.cjs:1) | Real short FFmpeg removal/ASS/audio plus geometry, errors, cancellation/UI contracts |
| Modify | [README](/D:/OneFl/README.md:57), [session](/D:/OneFl/.agents/SESSION_STATE.md:1) | Setup, evidence and limitations |
| Create | [review](/D:/OneFl/docs/reviews/2026-10-22-video-text-logo-cleanup.md:1) | Actual evidence and operator usage |

## Atomic execution tasks

1. Write schema/mask failing tests in `tests/test_video_cleanup.py:1-140`: reject NaN/outside/oversized/more than 12 regions, validate temporal reference, support inpaint mode. Run `backend/.venv/Scripts/python.exe -m pytest tests/test_video_cleanup.py -q -p no:cacheprovider --basetemp=tmp/video-cleanup/red` with disposable DATABASE_URL; expect red.
2. Add schemas in `backend/app/schemas/video_cleanup.py:1-100` and burn nesting in `translation.py:41-53`. Inputs are normalized x/y/width/height plus reference_time/track; geometry never becomes raw FFmpeg text. Repeat tests; expect schema cases pass.
3. Download/install optional cleanup libraries into workspace-managed environment, inspect actual RapidOCR API/config and explicitly prepare models under `data/models/video_cleanup`. Keep .env unchanged and existing package versions where possible. Verify package import/version and OCR on a generated Chinese-text image. No silent provider substitution.
4. Implement OCR adapter `cleanup_ocr.py:1-130` and setup script. Configure CPU threads, max OCR image side and CJK filtering; load only existing manifest-listed model files. Test exact boxes/confidence filtering and explicit missing-model error; real OCR smoke must recognize Chinese sample.
5. Implement mask/tracker processor `video_cleanup.py:1-200`: fresh uint8 mask each frame, padded OCR polygons, manual rectangles and optional template tracking. Clip at borders, never mask >50% of frame, do not apply unconfident tracked boxes. Tests measure actual dirty vs reconstructed synthetic pixels and moving-logo locations; normal unmasked pixels preserved before encode.
6. Implement streaming worker `video_cleanup.py:200-380`: decode raw BGR frames at rational CFR from original segment, process frame by frame, encode with original segment audio and ASS applied last. Keep stderr on temporary files; kill/reap owned decoder/encoder on cancel/error; delete partial outputs. Verify a 3-s actual MP4 retains audio/dimensions/duration and gains translated ASS after cleanup. Add cancellation/failure regressions; expect no worker/process leak.
7. Integrate `video_burner.py:108-185` and `workflow_engine.py:393-470`: validated cleanup config in signature, existing partial/concat checkpoints, cleanup processing before subtitle filter and no duplicated segment seek. Preflight missing dependency/model/invalid config before enqueue through `pipeline.py:43-70`. Run cleanup + media integration + agent completion regressions; expect pass and legacy filter modes unchanged.
8. Implement frontend normalized-region helpers/types and unit tests, then `VideoCleanupEditor.tsx:1-240`: video preview/seek, pointer drawing, numeric percent inputs, remove region and track toggle. Respect display aspect ratio/mobile bounds and show selected reference time. `npm.cmd test` and `tsc --noEmit --incremental false` must pass.
9. Wire inpaint choice/OCR sampling/regions into `BurnProgressModal.tsx:1-270`, shared BurnOptions types/API/Studio callback. Reopen saved config, keep draft on 409, never imply covered preview equals cleaned output. Build isolated frontend copy (preserve live .next); browser exercises selection, saved API payload, manual cleanup burn, missing-model feedback and output download.
10. Run full backend + frontend/type checks, real OCR + synthetic/short existing-frame removal measurements and 3-s FFmpeg burn/concat tests. Use disposable DSN/output directories and owned fixtures; inspect output images/video and logs. Record measured scope, no generic guarantee for difficult backgrounds/rapid logos/10h RAM/drift.
11. Update README/review/session. If live backend is idle, back up current DB and refresh exact owned process so new API is available; never interrupt an active job or start a full live video. Stop owned fixtures, leave user servers healthy, report actual usage and any remaining limits.

## Review checkpoint and fallback

Proceed under user authorization with reversible edits and isolated checks. If optional models cannot be prepared, complete independently testable region removal and report automatic OCR as unavailable; never relabel blur/cover as successful inpainting. The performance budget prioritizes bounded memory/VRAM and correct duration over an unmeasured realtime claim. No commits, deletes of user media/venv/node_modules, profile reads, cloud uploads or paid calls.
