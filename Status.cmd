@echo off
setlocal
cd /d "%~dp0" || exit /b 1
".venv\Scripts\python.exe" -X utf8 -m src.desktop status
pause
