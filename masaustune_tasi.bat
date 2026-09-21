@echo off
setlocal EnableDelayedExpansion
chcp 65001 >nul
title REIS AI - Masaustune Tasi

cd /d "%~dp0"
set "SRC=%~dp0"
for %%I in ("%SRC:~0,-1%") do set "SRC_PARENT=%%~dpI" & set "SRC_NAME=%%~nxI"

set "DST_ROOT=%USERPROFILE%\Desktop"
set "DST=%DST_ROOT%\%SRC_NAME%"

echo ============================================================
echo   REIS AI Agent Masaustune Tasiniyor
echo ============================================================
echo.
echo   Kaynak: %SRC%
echo   Hedef:  %DST%
echo.

if /I "%SRC%"=="%DST%\" (
    echo   Zaten masaustundesiniz. Islem iptal.
    echo   %SRC%
    pause
    exit /b 0
)

if exist "%DST%" (
    echo   Dikkat: Hedef klasor zaten var. Eski sürüm silinecek.
    echo   Onaylamak icin bir tusa basin...
    pause >nul
    rmdir /s /q "%DST%" 2>nul
)

echo.
echo [1/2] Kopyalama basliyor... Bu islem 1-3 dakika surebilir.
echo       (.venv ve OllamaSetup.exe dahil ~1.3 GB dosya)
echo.

set "KOPYA_OK=0"
where robocopy >nul 2>nul
if not errorlevel 1 (
    robocopy "%SRC%" "%DST%" /E /COPY:DAT /DCOPY:DAT /R:2 /W:2 /MT:4 /NFL /NDL
    REM 0-7 basarili
    if !ERRORLEVEL! LEQ 7 set "KOPYA_OK=1"
) else (
    xcopy "%SRC%" "%DST%\" /E /H /I /C /Y
    if not errorlevel 1 set "KOPYA_OK=1"
)

if not "%KOPYA_OK%"=="1" (
    echo.
    echo   HATA: Kopyalama basarisiz. Klasor kullanımda olabilir.
    pause
    exit /b 1
)

echo.
echo [2/2] Kopyalama tamamlandi.
echo.

if exist "%DST%\start.bat" (
    echo   OK: %DST%\start.bat   ^<- Ajanı baslatmak icin cift tikla
    echo   OK: %DST%\setup.bat   ^<- Ilk kurulum icin cift tikla
) else (
    echo   UYARI: Hedefte batch dosyalari bulunamadi. Kopyalama eksik olabilir.
)

echo.
echo   Klasor simdi aciliyor...
timeout /t 2 /nobreak >nul
start "" explorer "%DST%"

echo.
echo ============================================================
echo   ISLEM TAMAMLANDI
echo ============================================================
echo.
echo   Artik proje Masaustunde: REIS_AI_AGENT
echo   Kullanmak icin %DST%\setup.bat'a sonra start.bat'a cift tikla.
echo.
pause
endlocal
