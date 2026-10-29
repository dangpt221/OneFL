# Resume runtime recovery plan

**Goal:** Load the already-tested resume fix into the user's idle backend and identify the missing legacy project's recovery inputs. Do not create a second dubbing job or lose existing metadata.

**Evidence:** User repeats 409. Live port 8000 OpenAPI still describes the old resume implementation, while source contains the idempotent fix. Both API and read-only current SQLite show one FAILED pipeline project and no queued/running jobs. Requested c317... exists only in root legacy DB with 6474 subtitle cues and one speaker; all its saved source/audio/subtitle file paths currently fail `is_file()`. No matching source video was found in repository media paths.

**Architecture/constraints:** No application code or schema change planned. Keep current/legacy databases separate, preserve metadata and missing file references, no TTS/provider call. Restart only verified idle backend PID 24708 (started 09:51:52), preserve frontend PID/port 3000. Back up both SQLite databases through sqlite backup before restart. Start from root with the already-used current backend SQLite DSN, normal local storage and existing `.env` credentials. Capture PID/logs and current project list before/after. Missing video location is requested asynchronously; do not invent a path/config or import incomplete legacy data while awaiting it.

## Atomic tasks

1. Save a credential-free diagnostic JSON and SQLite backups under `tmp/resume-runtime-recovery`. Read source using `mode=ro`; preserve live project/cue counts. Verify backup files open and contain the same project IDs/counts.
2. Recheck the exact backend process and empty active queue, stop only that idle process, launch the fixed API hidden with PID/log files. No frontend build/restart or DB merge. Command: `backend/.venv/Scripts/python.exe -m uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8000`; expected healthy API and new OpenAPI resume description.
3. Verify `/api/v1/projects` retains the same current data and frontend proxy reaches the restarted backend. Confirm original legacy DB metadata remains unchanged. Record that c317... still requires legacy recovery/source file; do not claim its dubbing succeeded.
4. Publish actual runtime evidence and a reproducible recovery inventory, update SESSION_STATE. If user supplies source path, inspect media and prepare a separate project restoration plan before any metadata merge; preserve all 6474 cues and other current projects.

## Fallback/checkpoint

If a job becomes active before restart, do not stop it. If the new server fails, use logs/backups for diagnosis and leave both DBs intact. Legacy import depends on the real source video location and a deliberate saved dubbing configuration, not guessed defaults. No repeated permission request for this idle restart: it is reversible work required by the repeated bug report.
