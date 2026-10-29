# Dubbing/subtitle readiness verification plan

**Goal:** Determine which requested video translation/dubbing capabilities exist and whether speech and subtitle timing actually match. Separate mechanical timing evidence from ASR/translation/voice quality.

**Architecture & constraints:** Review only; preserve application behavior and user changes. Use disposable SQLite/storage and generated seconds of media, with real FFmpeg and synthetic tone providers. No model downloads, provider charges, live projects, GPU concurrency changes or claims about 10-hour/50-GB performance. Production DB/WebSocket contracts stay unchanged; generated artifacts stay under `tmp/dubbing-review`.

**Skills:** writing-plans, code-review-excellence, onefl-media-verification, verification-before-completion.

## File impact matrix

| Action | File |
| --- | --- |
| Read | [TTS timeline](/D:/OneFl/backend/app/services/tts_service.py:457), [ASR](/D:/OneFl/backend/app/services/asr_service.py:65), [subtitle export](/D:/OneFl/backend/app/services/subtitle_generator.py:90) |
| Read | [player](/D:/OneFl/frontend/src/components/VideoPlayer.tsx:85), [editor](/D:/OneFl/frontend/src/components/SubtitleEditor.tsx:315), [subtitle index](/D:/OneFl/frontend/src/lib/subtitleTimeline.ts:1) |
| Create | [standalone audit probe](/D:/OneFl/docs/reviews/2026-10-21-dubbing-sync-probes.py) |
| Create | [findings report](/D:/OneFl/docs/reviews/2026-10-21-dubbing-subtitle-readiness.md) |
| Modify | [task ledger](/D:/OneFl/.agents/SESSION_STATE.md:1) |

## Atomic tasks

1. Read source and match capabilities to Architecture/Translation specification. Trace `dub_project_timeline(cues, duration, output) -> Path`, ASS event times and player active-cue selection. Verify with `rg -n 'available =|word_timestamps|next_start|volume=|activeCueAt' backend/app/services frontend/src/components/VideoPlayer.tsx`; expected: concrete code references for each finding.
2. Create `async run_case(...) -> dict` in the audit probe. Set isolated environment before app imports; stub only speech synthesis with FFmpeg tones, generate a short audio timeline, decode PCM, measure tone onset/end and expected subtitle windows. Cover short speech, gap after cue, tempo fitting, overflow rejection and overlapping cues. Let unexpected exceptions fail the probe; capture only expected overflow as an explicit observation. Command: `backend/.venv/Scripts/python.exe docs/reviews/2026-10-21-dubbing-sync-probes.py`; expected: JSON observations and artifacts, no provider/network/database access. This is an audit, not a test claiming all timing semantics pass.
3. Run fresh acceptance: `$env:DATABASE_URL='sqlite+aiosqlite:///:memory:'; backend/.venv/Scripts/python.exe -m pytest tests/test_audio_timeline.py tests/test_media_integration.py tests/test_diarization.py -q -p no:cacheprovider --basetemp=tmp/dubbing-review/pytest`; expected: zero failures. These establish orchestration/media behavior, not natural-language correctness.
4. Publish measured findings and feature gaps with source references; mark ledger completed. Verify the probe compiles and inspect JSON/output files. Explicitly disclose untested real models, human listening/translation judgments and long-media drift.

## Review checkpoint & fallback

The user's review request authorizes these read-only inspections and disposable probes. Report results before any redesign, live provider evaluation or production media operation. If FFmpeg is unavailable, report the failed command and limit conclusions to source review; never replace measured output with assumptions. Revert only newly created review artifacts if needed, preserving all existing code and user changes.
