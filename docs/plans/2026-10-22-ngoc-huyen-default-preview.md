# Ngọc Huyền default and TTS preview repair

## Goal
Set the existing `vieneu-ngoc-huyen` profile as the default narrator across new project/API/Agent/UI flows and fix the reported preview502 caused by Edge WebSocket403. Preserve explicit saved voices, speaker selections, media and the currently active user download.

## Architecture and constraints
No ASR/translation/render algorithm or database schema change. Use the existing Ngọc Huyền Edge profile (Hoài My with pitch/rate/EQ); do not claim a Vbee engine. Official edge-tts7.3.1 replaces obsolete7.2.8 protocol; do not hand-patch credentials/hosts/token. Tests isolate DSN/storage. Speech verification uses only a short public catalog sample. No whole video render/provider spend. Never restart active live worker; first complete/review code and evidence, then reload only if idle. Existing current-project narrator may be updated by its public API only after backup and guards establish no dubbing config/audio/speaker overrides; retain active job/media refs.

## File impact matrix
| Action | Files | Purpose |
| --- | --- | --- |
| Modify | `backend/app/config.py:140-150`, `.env.example:76`, targeted `.env` setting | Canonical configured default |
| Modify | `backend/app/models/project.py:34`, `models/speaker.py:27`, `schemas/project.py:57`, `schemas/speaker.py:16-47`, `schemas/tts.py:8` | Defaults agree with configuration |
| Modify | `backend/app/api/v1/projects.py:326`, `api/v1/speakers.py:100`, `services/workflow_engine.py:177`, `agent/tools.py:71,355` | Remove inconsistent implicit Hoài My defaults; retain explicit/gender-specific voices |
| Modify | `backend/app/services/tts_service.py:335-460`, `api/v1/tts.py:53-83`, `requirements.txt:10`, `pyproject.toml:16` | Configured catalog/default calls, official protocol upgrade and actionable preview error |
| Modify/Create | `frontend/src/components/DubbingModal.tsx:18-110`, `SpeakerMatrixModal.tsx:150,685-762`, `lib/ttsPresentation.ts`, `tests/tts-default-regressions.cjs` | Shared default selection, safe asynchronous preview errors, female fallback |
| Create/Test | `tests/test_default_voice.py`, `tests/test_tts_provider.py`, `frontend/tests/tts-default-browser.cjs` | Default/create/preserve choices, provider failures/retry, preview/cache/voice selection |
| Modify/Create | `README.md`, `.agents/SESSION_STATE.md`, `docs/reviews/2026-10-22-ngoc-huyen-default-preview.md` | Usage, source attribution and actual runtime limits |

## Atomic tasks
1. Add failing default tests for configured Ngọc Huyền, ORM persisted project/speaker, HTTP preview/dub schema, catalog flag, Agent and explicit saved voice preservation. Command: `$env:DATABASE_URL='sqlite+aiosqlite:///:memory:'; backend/.venv/Scripts/python.exe -m pytest tests/test_default_voice.py -q -p no:cacheprovider --basetemp=tmp/ngoc-huyen/default-red`; expect feature failures before changing implementation.
2. Set config/model/schema/fallback defaults using settings, update only DEFAULT_TTS_VOICE in active .env with a private backup, no mass conversion of themed speaker presets. Re-run task1: pass; existing explicit voices/male profiles stay explicit.
3. Add provider failure tests to `test_tts_provider.py`: failing Edge connection produces a safe actionable message, no output or fallback voice, cancellation propagates; preview uses requested/configured voice. Upgrade manifests to>=7.3.1 and implement narrow error handling in existing service/router. Run focused TTS/media tests: pass.
4. Download/install the official release using current venv without changing unrelated dependencies. Validate a short actual Ngọc Huyền preview and decode audio. Keep network probes bounded; no live full project dubbing. Record package version and audio/cache endpoint evidence.
5. Add frontend default helper tests before implementation. Use saved last_dub_config.voice then project.default_voice then catalog default/Ngọc Huyền fallback; surface backend preview details and ignore stale success/error after voice change/close. Run `npm.cmd test` and `tsc --noEmit --incremental false`: exit0. Speaker female implicit fallback becomes Ngọc Huyền; male and explicit selection preserved.
6. Browser fixture tests verify default selected, payload, saved voice reopen, actionable preview error/draft and stale-response ownership. Full backend suite + isolated frontend production build. Preserve live .next. Update report/state; inspect live job before any reload. If still active, retain worker and accurately report pending reload rather than interrupt its download.

## Checkpoint and fallback
The user explicitly requested setting the default and fixing preview. Proceed with reversible changes/tests under that authorization. Root owns frontend/env/runtime/docs; agents have disjoint backend default and TTS provider files. No destructive git, project reset/delete, paid voice, or source downloads. If Microsoft remains unavailable, retain explicit provider failure (no silent alternate voice) and document real result. If live download remains active, keep it running; do not claim old process has loaded changed code.
