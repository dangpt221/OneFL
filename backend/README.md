# OneFL backend

FastAPI application in `app`, installed from `pyproject.toml`. Run from the repository root:

```powershell
backend/.venv/Scripts/python.exe -m pip install -e './backend[dev]'
backend/.venv/Scripts/python.exe -m uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8000
```

Configuration loads from the repository `.env` or environment variables. `ONEFL_ROOT_DIR` overrides the root in containers. Relative SQLite URLs resolve under `backend`; use an explicit absolute DSN when needed. Startup applies migrations only to the configured engine, then starts the durable worker.

See the [root operating guide](../README.md) for access tokens, queue recovery, local media storage, optional diarization/vision, production requirements, backups and isolated verification commands.
