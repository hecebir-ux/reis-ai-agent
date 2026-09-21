@echo off
setlocal EnableDelayedExpansion
chcp 65001 >nul
title REIS AI AUTONOMOUS AGENT - Kurulum

set PYTHONIOENCODING=utf-8
set PYTHONUTF8=1

echo ============================================================
echo   REIS AI AUTONOMOUS AGENT - Kurulum
echo ============================================================
echo.

cd /d "%~dp0"

echo [1/7] Python kontrol ediliyor...
where python >nul 2>nul
if errorlevel 1 (
    echo   HATA: python bulunamadi. Python 3.10+ kurun: https://python.org
    pause
    exit /b 1
)
for /f "tokens=*" %%v in ('python --version 2^>^&1') do set PYVER=%%v
echo   OK: %PYVER%

echo.
echo [2/7] Sanal Python ortami (.venv) hazirlaniyor...
if not exist ".venv\Scripts\python.exe" (
    echo   Sanal ortam olusturuluyor...
    python -m venv .venv
    if errorlevel 1 (
        echo   HATA: Sanal ortam olusturulamadi.
        pause
        exit /b 1
    )
) else (
    echo   OK: .venv zaten var
)
set "PYEXE=%~dp0.venv\Scripts\python.exe"
set "PIPEXE=%~dp0.venv\Scripts\pip.exe"
"%PYEXE%" -m pip install --upgrade pip >nul
echo   OK

echo.
echo [3/7] Gerekli paketler kuruluyor...
"%PIPEXE%" install -r "%~dp0requirements.txt"
if errorlevel 1 (
    echo   HATA: Paket kurulumu basarisiz. Internet baglantisini kontrol edin.
    pause
    exit /b 1
)
echo   OK

echo.
echo [4/7] Ollama kurulumu kontrol ediliyor...
set "OLLAMA_EXE="
if exist "%LOCALAPPDATA%\Programs\Ollama\ollama.exe" set "OLLAMA_EXE=%LOCALAPPDATA%\Programs\Ollama\ollama.exe"
if exist "C:\Program Files\Ollama\ollama.exe" set "OLLAMA_EXE=C:\Program Files\Ollama\ollama.exe"
if defined OLLAMA_EXE (
    echo   OK: Ollama bulundu
    for /f "tokens=*" %%v in ('"!OLLAMA_EXE!" --version 2^>^&1') do echo   Surum: %%v
    goto :OLLAMA_OK
)

REM Eger yok ve yanlislikla silindiyse, beraberindeki kurulum dosyasini kullan
if exist "%~dp0OllamaSetup.exe" (
    echo   Ollama kurulu degil. Paket icindeki kurulum kullaniliyor...
    echo   (Elevated izinler istenebilir)
    start "" /wait "%~dp0OllamaSetup.exe" /VERYSILENT /SUPPRESSMSGBOXES /NORESTART /SP-
    set "OLLAMA_EXE="
    if exist "%LOCALAPPDATA%\Programs\Ollama\ollama.exe" set "OLLAMA_EXE=%LOCALAPPDATA%\Programs\Ollama\ollama.exe"
    if exist "C:\Program Files\Ollama\ollama.exe" set "OLLAMA_EXE=C:\Program Files\Ollama\ollama.exe"
    if defined OLLAMA_EXE (
        echo   OK: Ollama kuruldu
        for /f "tokens=*" %%v in ('"!OLLAMA_EXE!" --version 2^>^&1') do echo   Surum: %%v
        goto :OLLAMA_OK
    )
)

REM Hala yoksa kullaniciya soyle
echo.
echo   Dikkat: Otomatik kurulum basarisiz oldu.
echo   Lutfen kendiniz kurun: https://ollama.com/download
echo   Kurulumdan sonra setup.bat'i tekrar calistirin.

:OLLAMA_OK

echo.
echo [5/7] Ollama servisi baslatiliyor...
powershell -Command "try { $r = Invoke-WebRequest -Uri 'http://127.0.0.1:11434/api/tags' -UseBasicParsing -TimeoutSec 3; if ($r.StatusCode -eq 200) { exit 0 } } catch { exit 1 }" >nul 2>nul
if not errorlevel 1 goto :OLLAMA_API_SETUP_OK

echo   Ollama API calismiyor. Ollama baslatiliyor...
if exist "%LOCALAPPDATA%\Programs\Ollama\ollama app.exe" (
    start "" "%LOCALAPPDATA%\Programs\Ollama\ollama app.exe"
    echo   Ollama App (kullanici) baslatildi.
    goto :WAIT_OLLAMA_SETUP_LOOP
)
if exist "C:\Program Files\Ollama\ollama app.exe" (
    start "" "C:\Program Files\Ollama\ollama app.exe"
    echo   Ollama App (sistem) baslatildi.
    goto :WAIT_OLLAMA_SETUP_LOOP
)
if defined OLLAMA_EXE (
    start "" /B "!OLLAMA_EXE!" serve
    echo   ollama serve (arka plan) baslatildi.
    goto :WAIT_OLLAMA_SETUP_LOOP
)

:WAIT_OLLAMA_SETUP_LOOP
echo.
echo   Ollama hazir olana kadar bekleniyor (maksimum 60 sn)...
set /a CNT=0
:WAIT_OLLAMA_SETUP
set /a CNT+=1
ping -n 4 127.0.0.1 >nul
powershell -Command "try { $r = Invoke-WebRequest -Uri 'http://127.0.0.1:11434/api/tags' -UseBasicParsing -TimeoutSec 3; if ($r.StatusCode -eq 200) { exit 0 } } catch { exit 1 }" >nul 2>nul
if not errorlevel 1 (
    echo   OK: Ollama API hazir. (!CNT! deneme)
    goto :OLLAMA_READY_SETUP
)
if !CNT! GEQ 20 (
    echo   [UYARI] 60 sn sonunda Ollama hala hazir degil.
    echo           Elle baslatiyorsaniz start.bat'i tekrar calistirin.
    goto :OLLAMA_READY_SETUP
)
echo   Bekleniyor... (!CNT!. deneme)
goto :WAIT_OLLAMA_SETUP

:OLLAMA_API_SETUP_OK
echo   OK: Ollama API zaten calisiyor

:OLLAMA_READY_SETUP

echo.
echo [6/7] Klasorler olusturuluyor...
if not exist "%~dp0workspace" mkdir "%~dp0workspace"
if not exist "%~dp0memory" mkdir "%~dp0memory"
if not exist "%~dp0logs" mkdir "%~dp0logs"
echo   OK

echo.
echo [7/7] .env dosyasi hazirlaniyor...
if not exist "%~dp0.env" (
    copy "%~dp0.env.example" "%~dp0.env" >nul
    echo   OK: .env olusturuldu
) else (
    echo   OK: .env zaten var
)

echo.
echo ============================================================
echo   KURULUM TAMAMLANDI
echo ============================================================
echo.
echo   Python: .venv kullaniliyor
if defined OLLAMA_EXE echo   Ollama: !OLLAMA_EXE!
echo.
echo   Baslatmak icin: start.bat
echo.
echo   Ilk calistirmada model otomatik test edilecek.
echo   Gerekli model yoksa inmesi birkac dakika surebilir.
echo.
pause
endlocal
