@echo off
echo ========================================================
echo  Starting OneFL Video Translation Backend (FastAPI)
echo ========================================================
cd /d "%~dp0backend"
if exist ".venv\Scripts\python.exe" (
    .venv\Scripts\python.exe -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
) else (
    py -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
)
pause
