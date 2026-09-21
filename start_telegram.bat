@echo off
chcp 65001 >nul
cd /d "%~dp0"
set PYTHONIOENCODING=utf-8

if exist ".venv\Scripts\python.exe" (
  set "PY=.venv\Scripts\python.exe"
) else (
  set "PY=python"
)

echo REIS AI Telegram Bot baslatiliyor...
"%PY%" telegram_bot.py
if errorlevel 1 pause
