@echo off
setlocal
cd /d "%~dp0" || exit /b 1
if not exist ".venv\Scripts\python.exe" (
  echo Please run Setup.cmd first.
  pause
  exit /b 1
)
".venv\Scripts\python.exe" -X utf8 -m src.desktop start %*
if errorlevel 1 pause
