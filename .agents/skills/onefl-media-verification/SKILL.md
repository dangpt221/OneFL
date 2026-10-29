---
name: onefl-media-verification
description: Verify OneFL media, job and UI/backend synchronization changes using isolated fixtures, real short FFmpeg processing and explicit provider boundaries.
---

# OneFL media verification

Read the verification section of [the repository guide](../../../README.md) and the relevant acceptance tests before choosing checks. Preserve the working `.env`, media and database; set a disposable DSN before importing the application. Do not reuse a live project for probes.

Run from the repository root in PowerShell:

```powershell
$env:DATABASE_URL='sqlite+aiosqlite:///:memory:'
backend/.venv/Scripts/python.exe -m pytest tests -q -p no:cacheprovider --basetemp=tmp/media-verification
```

When changing ASR/export/burn handoff, run `tests/test_agent_completion.py` and `tests/test_media_integration.py`. The short-media chain must probe an actual output file, compare duration, check persisted project URLs/cue counts and terminal job ownership. Assert cancellation and missing-provider failures instead of accepting copied source, silent speech or fabricated dialogue as output.

For UI synchronization changes, use `tests/e2e_backend.py` and `frontend/tests/browser-flow.cjs` as described in the README. Confirm fixture ports are free, start only owned background helpers, and stop them after verification. Keep browser results, traces and screenshots under `tmp`; distinguish viewport checks from testing a physical device. For layout/status changes, also run frontend regressions, TypeScript and production build.

Use deterministic external provider fixtures to verify orchestration, and explicitly identify them in results. Live model quality, NVENC performance, PostgreSQL/Docker/HTTPS deployment and 10-hour/50-GB memory/A-V drift need separate evidence on representative inputs. A three-second CPU render proves none of those measurements.

Audit scripts in `docs/reviews` can assert historical defects. Current acceptance lives in `tests` and `frontend/tests`; do not count historical defect reproductions as passing product tests.
