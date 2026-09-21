@echo off
setlocal EnableDelayedExpansion
chcp 65001 >nul
title REIS AI AUTONOMOUS AGENT

set PYTHONIOENCODING=utf-8
set PYTHONUTF8=1

cd /d "%~dp0"

REM Ollama PATH'e ekle (varsa)
if exist "%LOCALAPPDATA%\Programs\Ollama" set "PATH=%LOCALAPPDATA%\Programs\Ollama;%PATH%"
if exist "C:\Program Files\Ollama" set "PATH=C:\Program Files\Ollama;%PATH%"

REM Ollama API calisiyor mu kontrol et, calismiyorsa baslat
echo [Kontrol 1/2] Ollama API...
powershell -Command "try { $r = Invoke-WebRequest -Uri 'http://127.0.0.1:11434/api/tags' -UseBasicParsing -TimeoutSec 3; if ($r.StatusCode -eq 200) { exit 0 } } catch { exit 1 }" >nul 2>nul
if not errorlevel 1 goto :OLLAMA_API_ALREADY_RUNNING

echo   API kapali. Ollama baslatiliyor...
if exist "%LOCALAPPDATA%\Programs\Ollama\ollama app.exe" (
    start "" "%LOCALAPPDATA%\Programs\Ollama\ollama app.exe"
    echo   Baslatildi: Ollama App (kullanici modu)
    goto :WAIT_OLLAMA_LOOP
)
if exist "C:\Program Files\Ollama\ollama app.exe" (
    start "" "C:\Program Files\Ollama\ollama app.exe"
    echo   Baslatildi: Ollama App (sistem)
    goto :WAIT_OLLAMA_LOOP
)
if exist "%LOCALAPPDATA%\Programs\Ollama\ollama.exe" (
    start "" /B "%LOCALAPPDATA%\Programs\Ollama\ollama.exe" serve
    echo   Baslatildi: ollama serve (arka plan)
    goto :WAIT_OLLAMA_LOOP
)
where ollama >nul 2>nul
if not errorlevel 1 (
    start "" /B ollama serve
    echo   Baslatildi: ollama serve (PATH)
    goto :WAIT_OLLAMA_LOOP
)

echo.
echo   [HATA] Ollama bulunamadi. setup.bat'i tekrar calistirin.
echo   Elle indirme: https://ollama.com/download
pause
exit /b 1

:WAIT_OLLAMA_LOOP
echo.
echo   Ollama hazir olana kadar bekleniyor (maksimum 60 sn)...
set /a CNT=0
:WAIT_OLLAMA
set /a CNT+=1
ping -n 4 127.0.0.1 >nul
powershell -Command "try { $r = Invoke-WebRequest -Uri 'http://127.0.0.1:11434/api/tags' -UseBasicParsing -TimeoutSec 3; if ($r.StatusCode -eq 200) { exit 0 } } catch { exit 1 }" >nul 2>nul
if not errorlevel 1 (
    echo   OK: Ollama API hazir. (!CNT! deneme)
    goto :OLLAMA_READY
)
if !CNT! GEQ 20 (
    echo   [UYARI] 60 sn sonunda Ollama hala hazir degil. Devam ediliyor...
    echo           Eger sorun surerse: Ollama App'i elle baslatin.
    goto :OLLAMA_READY
)
echo   Bekleniyor... (!CNT!. deneme)
goto :WAIT_OLLAMA

:OLLAMA_API_ALREADY_RUNNING
echo   OK: Ollama API zaten calisiyor.

:OLLAMA_READY

REM Kullaniciya virtual env yoksa setup.once hatirlat
echo.
echo [Kontrol 2/2] Python ortami...
if not exist ".venv\Scripts\python.exe" (
    echo   [UYARI] .venv bulunamadi. Once setup.bat calistirilmasi onerilir.
    echo   Sistem Python'u deneniyor...
    where python >nul 2>nul
    if errorlevel 1 (
        echo.
        echo   [HATA] Python bulunamadi. setup.bat'i calistirin.
        pause
        exit /b 1
    )
    ping -n 4 127.0.0.1 >nul
    set "PYEXE=python"
) else (
    echo   OK: .venv bulundu.
    set "PYEXE=%~dp0.venv\Scripts\python.exe"
)

echo.
echo ============================================================
echo   REIS AI ULTRA — UI + SELF-EVOLUTION + TELEGRAM
echo   Arayuz: http://127.0.0.1:8765/
echo ============================================================
echo.
"%PYEXE%" agent.py --ui
if errorlevel 1 (
    echo.
    echo ============================================================
    echo  [HATA] Agent baslatilamadi veya hata ile kapandi.
    echo  Oneriler:
    echo   1. setup.bat'i YONETICI olarak calistirin
    echo   2. Ollama App calisiyor mu kontrol edin
    echo   3. Model icin: ollama pull qwen2.5-coder
    echo   4. Alternatif CLI: "%PYEXE%" main.py --cli
    echo ============================================================
    echo.
    pause
)
endlocal
