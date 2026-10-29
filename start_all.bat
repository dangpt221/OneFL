@echo off
echo ========================================================
echo  Starting OneFL Studio (Backend & Frontend)
echo ========================================================
start "OneFL Backend (FastAPI)" "%~dp0start_backend.bat"
start "OneFL Frontend (Next.js)" "%~dp0start_frontend.bat"
echo Both Backend (http://localhost:8000) and Frontend (http://localhost:3000) are starting...
