@echo off
echo ========================================================
echo  Starting OneFL Studio Frontend (Next.js 14)
echo ========================================================
cd /d "%~dp0frontend"
npm run dev -- --hostname 127.0.0.1
pause
