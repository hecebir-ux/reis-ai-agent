@echo off
setlocal EnableDelayedExpansion
chcp 65001 >nul
title REIS AI — Uygulama Derleme

cd /d "%~dp0"
set PYTHONIOENCODING=utf-8
set PYTHONUTF8=1

if not exist ".venv\Scripts\python.exe" (
    echo [.venv yok] Once setup.bat calistirin.
    pause
    exit /b 1
)

set "PY=.venv\Scripts\python.exe"
set "PIP=.venv\Scripts\pip.exe"

echo ============================================================
echo   REIS AI Windows Uygulamasi Derleniyor
echo ============================================================
echo.

echo [1/3] PyInstaller kuruluyor...
"%PIP%" install -q "pyinstaller>=6.0"
if errorlevel 1 (
    echo HATA: pyinstaller kurulamadi.
    pause
    exit /b 1
)

echo [2/3] Onceki dist temizleniyor...
if exist "dist\REIS_AI" rmdir /s /q "dist\REIS_AI"
if exist "build\reis_ai" rmdir /s /q "build\reis_ai"

echo [3/3] EXE uretiliyor (biraz surebilir)...
"%PY%" -m PyInstaller --noconfirm --clean reis_ai.spec
if errorlevel 1 (
    echo.
    echo HATA: Derleme basarisiz.
    pause
    exit /b 1
)

REM Calisma klasorleri
mkdir "dist\REIS_AI\workspace" 2>nul
mkdir "dist\REIS_AI\memory" 2>nul
mkdir "dist\REIS_AI\logs" 2>nul
mkdir "dist\REIS_AI\database" 2>nul
mkdir "dist\REIS_AI\backups" 2>nul
mkdir "dist\REIS_AI\cache" 2>nul
mkdir "dist\REIS_AI\plugins" 2>nul
mkdir "dist\REIS_AI\projects" 2>nul

if exist ".env" copy /Y ".env" "dist\REIS_AI\.env" >nul
if exist ".env.example" copy /Y ".env.example" "dist\REIS_AI\.env.example" >nul

REM Masaustu baslatici
(
echo @echo off
echo cd /d "%%~dp0"
echo start "" "%%~dp0REIS_AI.exe"
) > "dist\REIS_AI\BASLAT.bat"

echo.
echo ============================================================
echo   TAMAM
echo   Uygulama: %~dp0dist\REIS_AI\REIS_AI.exe
echo   Baslat:   %~dp0dist\REIS_AI\BASLAT.bat
echo   Arayuz:   http://127.0.0.1:8765/
echo ============================================================
echo.
echo Masaustune kisayol olusturmak icin: create_desktop_shortcut.bat
echo.
pause
endlocal
